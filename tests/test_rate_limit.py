from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.rate_limit import RateLimitMiddleware


def test_rate_limiting_middleware():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=3)

    @app.get("/v1/test")
    def test_endpoint():
        return {"ok": True}

    @app.get("/other")
    def other_endpoint():
        return {"ok": True}

    client = TestClient(app)

    # Non-v1 path should be exempt from rate limiting
    for _ in range(5):
        resp = client.get("/other")
        assert resp.status_code == 200

    # /v1/ path should allow exactly 3 requests within the window
    for _ in range(3):
        resp = client.get("/v1/test")
        assert resp.status_code == 200

    # 4th request should get 429
    resp = client.get("/v1/test")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.json()["detail"].startswith("Rate limit exceeded")


def test_rate_limit_disabled():
    app = FastAPI()
    # 0 disables rate limit
    app.add_middleware(RateLimitMiddleware, requests_per_minute=0)

    @app.get("/v1/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    for _ in range(10):
        resp = client.get("/v1/test")
        assert resp.status_code == 200
