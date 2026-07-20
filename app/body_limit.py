"""ASGI request-body size enforcement.

The middleware checks ``Content-Length`` before reading when available and also
counts streamed/chunked request bodies. Oversized requests are rejected before
JSON parsing or base64 image decoding can amplify memory use.
"""

from __future__ import annotations

import json
from typing import Any


class RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(self, app: Any, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max(int(max_bytes), 1)

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        raw_lengths = [
            value for key, value in scope.get("headers", []) if key.lower() == b"content-length"
        ]
        if len(set(raw_lengths)) > 1:
            await self._reject(
                send, 400, "Conflicting Content-Length headers.", scope.get("http_version")
            )
            return
        if raw_lengths:
            try:
                content_length = int(raw_lengths[0])
            except ValueError:
                await self._reject(
                    send, 400, "Invalid Content-Length header.", scope.get("http_version")
                )
                return
            if content_length < 0:
                await self._reject(
                    send, 400, "Invalid Content-Length header.", scope.get("http_version")
                )
                return
            if content_length > self.max_bytes:
                await self._reject(send, 413, http_version=scope.get("http_version"))
                return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(send, 413, http_version=scope.get("http_version"))

    async def _reject(
        self,
        send,
        status: int,
        detail: str | None = None,
        http_version: str | None = None,
    ) -> None:
        message = detail or f"Request body exceeds the {self.max_bytes}-byte limit."
        body = json.dumps({"detail": message}, separators=(",", ":")).encode("utf-8")
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if http_version in {"1.0", "1.1"}:
            # The unread remainder of an oversized HTTP/1 request must not be
            # interpreted as the next request on a persistent connection.
            headers.append((b"connection", b"close"))
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": body})
