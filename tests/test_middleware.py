import ipaddress

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.middleware import IngressRateLimitMiddleware, client_ip


def make_request(peer: str, forwarded: str) -> Request:
    scope = {
        "type": "http",
        "headers": [(b"x-real-ip", forwarded.encode())],
        "client": (peer, 1234),
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    }
    return Request(scope)


def test_forwarded_identity_is_used_only_from_configured_proxy(monkeypatch):
    monkeypatch.setenv("TOIR_TRUSTED_PROXY_IP", "10.0.0.2")
    assert client_ip(make_request("10.0.0.2", "198.51.100.5")) == "198.51.100.5"
    assert client_ip(make_request("203.0.113.8", "198.51.100.5")) == "203.0.113.8"
    assert client_ip(make_request("10.0.0.2", "attacker-value")) == "10.0.0.2"


def test_ingress_limiter_returns_retry_after_for_repeated_client():
    app = FastAPI()
    app.add_middleware(IngressRateLimitMiddleware, limit=1, window_seconds=60)

    @app.get("/protected")
    def protected():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/protected").status_code == 200
    blocked = client.get("/protected")
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]
