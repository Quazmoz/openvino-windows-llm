import asyncio

from fastapi.testclient import TestClient

from app.body_limit import RequestBodyLimitMiddleware
from app.config import Settings
from app.server import create_app


def test_server_rejects_oversized_content_length_before_json_parsing(tmp_path):
    models_file = tmp_path / "models.json"
    models_file.write_text("{}", encoding="utf-8")
    app = create_app(
        Settings(
            models_file=models_file,
            models_dir=tmp_path / "models",
            force_mock=True,
            max_request_body_mb=1,
        )
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            content=b"x" * (1024 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413
    assert "exceeds" in response.json()["detail"]
    assert response.headers["connection"] == "close"


def test_chunked_body_is_counted_without_content_length():
    async def downstream(scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestBodyLimitMiddleware(downstream, max_bytes=5)
    incoming = iter(
        [
            {"type": "http.request", "body": b"abc", "more_body": True},
            {"type": "http.request", "body": b"def", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(incoming)

    async def send(message):
        sent.append(message)

    asyncio.run(
        middleware(
            {"type": "http", "method": "POST", "path": "/v1/test", "headers": []},
            receive,
            send,
        )
    )
    assert sent[0]["status"] == 413
    assert b"Request body exceeds" in sent[1]["body"]


def test_invalid_or_conflicting_content_length_is_bad_request():
    async def downstream(_scope, _receive, _send):  # pragma: no cover - must not run
        raise AssertionError("invalid framing must be rejected before the application")

    async def run(headers):
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        middleware = RequestBodyLimitMiddleware(downstream, max_bytes=5)
        await middleware(
            {"type": "http", "method": "POST", "path": "/", "headers": headers},
            receive,
            send,
        )
        return sent

    invalid = asyncio.run(run([(b"content-length", b"not-a-number")]))
    assert invalid[0]["status"] == 400
    assert b"Invalid Content-Length" in invalid[1]["body"]

    conflicting = asyncio.run(run([(b"content-length", b"2"), (b"content-length", b"3")]))
    assert conflicting[0]["status"] == 400
    assert b"Conflicting Content-Length" in conflicting[1]["body"]


def test_http2_rejection_does_not_emit_forbidden_connection_header():
    async def downstream(_scope, _receive, _send):  # pragma: no cover - must not run
        raise AssertionError("oversized body must be rejected before the application")

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    middleware = RequestBodyLimitMiddleware(downstream, max_bytes=5)
    asyncio.run(
        middleware(
            {
                "type": "http",
                "http_version": "2",
                "method": "POST",
                "path": "/",
                "headers": [(b"content-length", b"6")],
            },
            receive,
            send,
        )
    )
    assert sent[0]["status"] == 413
    assert (b"connection", b"close") not in sent[0]["headers"]
