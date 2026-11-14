import importlib
import sqlite3
import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Import auth modules without package initializers that create the production DB or load ML models.
_missing_packages = {
    name: name not in sys.modules for name in ("app.services", "app.routers")
}
for _name, _subdir in (("app.services", "services"), ("app.routers", "routers")):
    if _missing_packages[_name]:
        _package = ModuleType(_name)
        _package.__path__ = [str(Path(__file__).parent / "app" / _subdir)]
        sys.modules[_name] = _package
try:
    _config = importlib.import_module("app.config")
    _original_settings = _config.settings
    _config.settings = SimpleNamespace(DB_PATH=Path(":memory:"))
    try:
        AuthService = importlib.import_module("app.services.auth").AuthService
        auth_router = importlib.import_module("app.routers.auth")
    finally:
        _config.settings = _original_settings
finally:
    for _name, _was_missing in _missing_packages.items():
        if _was_missing:
            sys.modules.pop(_name, None)


ACCESS_KEY = "B23456789C"


@pytest.fixture

def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TOIR_ACCESS_KEY_HASH", PasswordHasher().hash(ACCESS_KEY))
    monkeypatch.setenv("TOIR_ACCOUNT_ID", "emp-test")
    monkeypatch.setenv("TOIR_FULL_NAME", "Test Engineer")
    monkeypatch.setenv("TOIR_EMAIL", "test@example.com")
    monkeypatch.setenv("TOIR_ROLE", "engineer")
    monkeypatch.setattr(auth_router, "auth_service", AuthService(tmp_path / "auth.db"))
    app = FastAPI()
    app.include_router(auth_router.router)
    return TestClient(app)


def test_login_normalizes_key_and_returns_safe_account(client):
    response = client.post("/api/auth/login", json={"access_key": "b2 3456-789c"})

    assert response.status_code == 200
    body = response.json()
    assert body["account"] == {
        "id": "emp-test",
        "full_name": "Test Engineer",
        "email": "test@example.com",
        "role": "engineer",
        "permissions": ["scan"],
    }
    assert len(body["session_token"]) >= 40
    assert "key_hash" not in response.text
    assert "access_key" not in response.text

    with sqlite3.connect(auth_router.auth_service.db_path) as conn:
        stored = conn.execute("SELECT token_hash FROM auth_sessions").fetchone()[0]
    assert stored != body["session_token"]


def test_login_rejects_invalid_format_and_key(client):
    assert client.post("/api/auth/login", json={"access_key": "B234567890"}).status_code == 422

    response = client.post("/api/auth/login", json={"access_key": "C23456789D"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Ключ не подошёл."}


def test_me_logout_and_revocation(client):
    token = client.post("/api/auth/login", json={"access_key": ACCESS_KEY}).json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=headers).json()["id"] == "emp-test"
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_expired_session_is_unauthorized(client):
    token = client.post("/api/auth/login", json={"access_key": ACCESS_KEY}).json()["session_token"]
    with sqlite3.connect(auth_router.auth_service.db_path) as conn:
        conn.execute("UPDATE auth_sessions SET expires_at = '2000-01-01T00:00:00Z'")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_login_is_throttled_after_five_failures(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"access_key": "C23456789D"}).status_code == 401

    assert client.post("/api/auth/login", json={"access_key": "C23456789D"}).status_code == 429
    assert client.post("/api/auth/login", json={"access_key": ACCESS_KEY}).status_code == 429


def test_correct_key_on_fifth_attempt_is_still_checked(client):
    for _ in range(4):
        assert client.post("/api/auth/login", json={"access_key": "C23456789D"}).status_code == 401

    assert client.post("/api/auth/login", json={"access_key": ACCESS_KEY}).status_code == 200


def test_concurrent_login_failures_are_reserved_atomically(client):
    barrier = threading.Barrier(8)
    results = []

    def attempt():
        barrier.wait()
        results.append(client.post("/api/auth/login", json={"access_key": "C23456789D"}).status_code)

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert results.count(401) == 5
    assert results.count(429) == 3


def test_role_permissions_follow_contract(client, monkeypatch):
    monkeypatch.setenv("TOIR_ROLE", "dispatcher")
    account = client.post("/api/auth/login", json={"access_key": ACCESS_KEY}).json()["account"]
    assert account["permissions"] == ["scan", "dispatch"]
