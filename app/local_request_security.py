"""Browser-origin safeguards for state-changing localhost routes."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import HTTPException, Request

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_FORBIDDEN_DETAIL = "Cross-site browser requests are not allowed."


def _effective_port(scheme: str, port: int | None) -> int | None:
    if port is not None:
        return port
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _reject_cross_site() -> None:
    raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)


def require_safe_browser_origin(request: Request) -> None:
    """Reject cross-site browser mutations while allowing local API clients.

    Browsers attach Origin and Fetch Metadata headers to state-changing fetches
    and form submissions. CLI and SDK clients normally omit them, so those local
    integrations remain compatible. Requiring a loopback literal also blocks a
    DNS-rebinding origin whose Host header resolves to the loopback interface.
    """

    fetch_site = request.headers.get("sec-fetch-site", "").strip().lower()
    if fetch_site == "cross-site":
        _reject_cross_site()

    origin = request.headers.get("origin")
    if origin is None:
        return

    try:
        parsed = urlsplit(origin)
        origin_port = parsed.port
        request_port = request.url.port
    except ValueError:
        _reject_cross_site()
        return

    request_host = (request.url.hostname or "").lower()
    origin_host = (parsed.hostname or "").lower()
    request_scheme = request.url.scheme.lower()
    origin_scheme = parsed.scheme.lower()

    same_origin = (
        request_host in _LOOPBACK_HOSTS
        and origin_host == request_host
        and origin_scheme == request_scheme
        and _effective_port(origin_scheme, origin_port)
        == _effective_port(request_scheme, request_port)
    )
    if not same_origin:
        _reject_cross_site()
