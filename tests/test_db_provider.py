"""Unit tests for lazy PostgreSQL pool configuration and error handling."""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DB_ENV_NAMES = (
    "DATABASE_URL",
    "DATABASE_CATALOG_URL",
    "DATABASE_TASKS_URL",
    "DATABASE_EMPLOYEES_URL",
    "DATABASE_CREDENTIALS_URL",
)
DUMMY_DSN = "postgresql://pytest:pytest@127.0.0.1:1/pytest_no_connect"


@pytest.fixture
def isolated_db_env(monkeypatch):
    """Clear database DSNs for this test and restore the caller's environment."""
    for name in DB_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_db_module_imports_without_dsn_and_fails_only_when_pool_is_requested(
    isolated_db_env,
):
    db = importlib.import_module("app.services.db")

    provider = db.Pools()
    assert provider._pools == {}
    with pytest.raises(db.DatabaseNotConfigured):
        provider.get("catalog")


@pytest.mark.parametrize(
    ("key", "specific_env"),
    [
        ("tasks", "DATABASE_TASKS_URL"),
        ("employees", "DATABASE_EMPLOYEES_URL"),
        ("credentials", "DATABASE_CREDENTIALS_URL"),
    ],
)
def test_pools_fall_back_to_database_url_and_prefer_specific_dsn(
    monkeypatch, isolated_db_env, key, specific_env
):
    db = importlib.import_module("app.services.db")
    monkeypatch.setenv("DATABASE_URL", "  postgresql://app@db:5432/shared  ")

    fallback_provider = db.Pools()
    assert fallback_provider.get(key).dsn == "postgresql://app@db:5432/shared"

    monkeypatch.setenv(specific_env, f"postgresql://app@db:5432/{key}")
    specific_provider = db.Pools()
    assert specific_provider.get(key).dsn == f"postgresql://app@db:5432/{key}"


def test_pool_initialization_failure_becomes_database_unavailable(monkeypatch):
    db = importlib.import_module("app.services.db")

    class ConnectionFailure(Exception):
        pass

    def fail_to_create_pool(**_kwargs):
        raise ConnectionFailure("connection refused")

    monkeypatch.setattr(db, "_HAS_PSYCOPG", True)
    monkeypatch.setattr(
        db, "psycopg_pool", SimpleNamespace(ConnectionPool=fail_to_create_pool)
    )
    provider = db.PostgresPool(DUMMY_DSN, "catalog")

    with pytest.raises(db.DatabaseUnavailable) as exc_info:
        with provider.connection():
            pytest.fail("connection context must not yield after pool failure")

    assert isinstance(exc_info.value.__cause__, ConnectionFailure)


def test_pool_getconn_failure_becomes_database_unavailable():
    db = importlib.import_module("app.services.db")

    class BrokenPool:
        def getconn(self, *, timeout):
            assert timeout == 30
            raise OSError("pool exhausted")

        def putconn(self, _conn):
            pytest.fail("putconn must not run when getconn fails")

    provider = db.PostgresPool(DUMMY_DSN, "tasks")
    provider._pool = BrokenPool()

    with pytest.raises(db.DatabaseUnavailable, match="соединение"):
        with provider.connection():
            pytest.fail("connection context must not yield after getconn failure")


def test_database_error_handler_returns_http_503():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.main import postgres_error_handler

    db = importlib.import_module("app.services.db")
    app = FastAPI()
    app.add_exception_handler(db.DatabaseError, postgres_error_handler)

    @app.get("/database")
    def unavailable():
        raise db.DatabaseUnavailable("catalog unavailable")

    with TestClient(app) as client:
        response = client.get("/database")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Хранилище PostgreSQL временно недоступно."
    }


def test_storage_dependency_returns_http_503_when_storage_is_missing(monkeypatch):
    from fastapi import HTTPException

    from app.routers import _deps

    monkeypatch.setattr(_deps, "get_storage", lambda: None)

    with pytest.raises(HTTPException) as exc_info:
        _deps.storage_dep()

    assert exc_info.value.status_code == 503
    assert "DATABASE_URL" in exc_info.value.detail


@pytest.mark.parametrize("error_kind", ["sql", "programming"])
def test_cursor_only_translates_driver_errors(monkeypatch, error_kind):
    db = importlib.import_module("app.services.db")

    class FakePsycopgError(Exception):
        pass

    error = FakePsycopgError("invalid SQL") if error_kind == "sql" else ValueError(
        "application bug"
    )

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, _query):
            raise error

    class FakeConnection:
        rolled_back = False

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rolled_back = True

    class FakePool:
        def __init__(self, connection):
            self.connection = connection

        def getconn(self, *, timeout):
            assert timeout == 30
            return self.connection

        def putconn(self, connection):
            assert connection is self.connection

    connection = FakeConnection()
    provider = db.PostgresPool(DUMMY_DSN, "catalog")
    provider._pool = FakePool(connection)
    monkeypatch.setattr(db, "_HAS_PSYCOPG", True)
    monkeypatch.setattr(db, "psycopg", SimpleNamespace(Error=FakePsycopgError))

    if error_kind == "sql":
        with pytest.raises(db.DatabaseError) as exc_info:
            with provider.cursor() as cursor:
                cursor.execute("SELECT broken")
        assert exc_info.value.__cause__ is error
    else:
        with pytest.raises(ValueError, match="application bug") as exc_info:
            with provider.cursor() as cursor:
                cursor.execute("SELECT 1")
        assert exc_info.value is error

    assert connection.rolled_back
