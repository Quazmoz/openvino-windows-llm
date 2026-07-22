import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from app.desktop_operations_routes import _state_change_auth as desktop_state_change_auth
from app.local_request_security import require_safe_browser_origin
from app.onboarding_routes import _state_change_auth as onboarding_state_change_auth


def _request(
    *,
    host: str = "127.0.0.1:8000",
    origin: str | None = None,
    fetch_site: str | None = None,
) -> Request:
    headers = [(b"host", host.encode("ascii"))]
    if origin is not None:
        headers.append((b"origin", origin.encode("ascii")))
    if fetch_site is not None:
        headers.append((b"sec-fetch-site", fetch_site.encode("ascii")))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/mutation",
            "raw_path": b"/mutation",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 8000),
        }
    )


def test_non_browser_local_client_is_allowed():
    require_safe_browser_origin(_request())


def test_same_origin_loopback_browser_request_is_allowed():
    require_safe_browser_origin(_request(origin="http://127.0.0.1:8000", fetch_site="same-origin"))


@pytest.mark.parametrize(
    ("host", "origin", "fetch_site"),
    [
        ("127.0.0.1:8000", "https://attacker.example", "cross-site"),
        ("127.0.0.1:8000", "http://127.0.0.1:9000", "same-site"),
        ("attacker.example:8000", "http://attacker.example:8000", "same-origin"),
        ("127.0.0.1:8000", "null", "none"),
    ],
)
def test_unsafe_browser_origins_are_rejected(host, origin, fetch_site):
    with pytest.raises(HTTPException) as exc_info:
        require_safe_browser_origin(_request(host=host, origin=origin, fetch_site=fetch_site))
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "factory",
    [onboarding_state_change_auth, desktop_state_change_auth],
)
def test_state_change_dependencies_apply_origin_guard(factory):
    dependency = factory(SimpleNamespace(api_key=None))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            dependency(
                _request(origin="https://attacker.example", fetch_site="cross-site"),
                None,
            )
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize(
    "factory",
    [onboarding_state_change_auth, desktop_state_change_auth],
)
def test_state_change_dependencies_preserve_local_api_clients(factory):
    dependency = factory(SimpleNamespace(api_key=None))
    asyncio.run(dependency(_request(), None))
