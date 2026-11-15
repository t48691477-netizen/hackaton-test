"""Регрессии SQL/API-адаптеров для /front и Flask API без PostgreSQL."""

import sys
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.routers import front_compat
from app.services.db import DatabaseError, DatabaseUnavailable


@pytest.fixture
def front_client():
    app = FastAPI()
    app.include_router(front_compat.router)
    return TestClient(app)


def _report_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "equipment_id": "pump-1",
        "inspection_id": "insp-1",
        "status": "open",
        "comment": "",
        "photo_url": None,
        "result": {"defects": []},
        "assignee_id": None,
        "assignee_full_name": None,
        "started_at": None,
        "completed_at": None,
        "repair_comment": None,
        "created_at": datetime(2026, 11, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 15, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return row


def test_report_fields_match_tasks_schema_and_physical_pool(monkeypatch):
    expected_columns = {
        "id", "equipment_id", "inspection_id", "status", "comment", "photo_url",
        "result", "assignee_id", "assignee_full_name", "started_at", "completed_at",
        "repair_comment", "created_at", "updated_at",
    }
    selected_columns = {
        column.strip()
        for column in front_compat._FrontTasksRepo._FIELDS.replace("\n", "").split(",")
    }
    assert selected_columns == expected_columns
    schema_path = PROJECT_ROOT / "database" / "sql" / "tasks" / "001_schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    table = re.search(
        r"CREATE TABLE IF NOT EXISTS promscan\.reports\s*\((.*?)\n\);",
        schema,
        re.DOTALL,
    )
    assert table is not None
    schema_columns = {
        match.group(1)
        for match in re.finditer(r"^\s{4}([a-z_]+)\s+", table.group(1), re.MULTILINE)
    }
    assert selected_columns == schema_columns

    monkeypatch.setenv("DATABASE_URL", "postgresql://app@db:5432/catalog")
    monkeypatch.setenv("DATABASE_TASKS_URL", "postgresql://app@db:5432/tasks")
    monkeypatch.delenv("DATABASE_EMPLOYEES_URL", raising=False)

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class FakePool:
        dsn = "postgresql://app@db:5432/tasks"

        def cursor(self, **_kwargs):
            return FakeCursor()

    class FakePools:
        def __init__(self):
            self.requested = []
            self.pool = FakePool()

        def get(self, name):
            self.requested.append(name)
            return self.pool

    fake_pools = FakePools()
    repo = front_compat._FrontTasksRepo()
    repo._pools = fake_pools
    with repo._cursor():
        pass
    assert fake_pools.requested == ["tasks"]

    monkeypatch.setenv("DATABASE_TASKS_URL", "postgresql://app@db:5432/catalog")
    with pytest.raises(DatabaseUnavailable):
        with repo._cursor():
            pass

    monkeypatch.setenv("DATABASE_TASKS_URL", "postgresql://app@db:5432/tasks")
    stale_pool_repo = front_compat._FrontTasksRepo()
    stale_pool_repo._pools = FakePools()
    stale_pool_repo._pools.pool.dsn = "postgresql://app@db:5432/catalog"
    with pytest.raises(DatabaseUnavailable):
        with stale_pool_repo._cursor():
            pass

    monkeypatch.delenv("DATABASE_TASKS_URL")
    with pytest.raises(DatabaseUnavailable):
        with repo._cursor():
            pass


def test_front_routes_keep_contract_and_detailed_endpoint_is_removed(front_client, monkeypatch):
    row = _report_row()
    monkeypatch.setattr(front_compat._tasks_repo, "list_reports", lambda status=None: [row])
    monkeypatch.setattr(front_compat._tasks_repo, "get", lambda report_id: row)
    monkeypatch.setattr(front_compat._tasks_repo, "patch_status", lambda *args: (row, None))

    reports = front_client.get("/front/api/reports?status=open")
    assert reports.status_code == 200
    body = reports.json()[0]
    assert set(body) == {
        "id", "equipment_id", "inspection_id", "status", "comment", "photo_url",
        "result", "assignee", "started_at", "completed_at", "repair_comment",
        "created_at", "updated_at",
    }
    assert body["id"] == str(row["id"])

    assert front_client.get(f"/front/api/reports/{row['id']}").status_code == 200
    assert front_client.get("/front/api/reports?status=unknown").status_code == 422
    assert front_client.patch(
        f"/front/api/reports/{row['id']}/status", json={"status": "wrong"}
    ).status_code == 422
    assert front_client.post("/front/api/inspect/detailed").status_code == 404

    routes = {
        (method, route.path)
        for route in front_compat.router.routes
        for method in (route.methods or set())
    }
    assert {
        ("GET", "/front/api/equipment"),
        ("GET", "/front/api/equipment/{equipment_id}"),
        ("POST", "/front/api/inspect"),
        ("GET", "/front/api/reports"),
        ("GET", "/front/api/reports/{report_id}"),
        ("POST", "/front/api/reports"),
        ("PATCH", "/front/api/reports/{report_id}/status"),
        ("POST", "/front/api/mail/access-key"),
    } <= routes


def test_rejected_status_can_only_be_repeated_not_set_as_a_new_transition(
    front_client, monkeypatch
):
    rejected = _report_row(status="rejected")
    monkeypatch.setattr(
        front_compat._tasks_repo,
        "patch_status",
        lambda *_args: (rejected, None),
    )

    repeated = front_client.patch(
        f"/front/api/reports/{rejected['id']}/status", json={"status": "rejected"}
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "rejected"

    opened = _report_row(status="open")
    monkeypatch.setattr(
        front_compat._tasks_repo,
        "patch_status",
        lambda *_args: (None, "invalid_status"),
    )
    new_rejection = front_client.patch(
        f"/front/api/reports/{opened['id']}/status", json={"status": "rejected"}
    )
    assert new_rejection.status_code == 422


def test_front_database_unavailable_returns_503(front_client, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise DatabaseUnavailable("tasks: unavailable")

    monkeypatch.setattr(front_compat._tasks_repo, "list_reports", unavailable)
    response = front_client.get("/front/api/reports")
    assert response.status_code == 503
    assert response.json() == {"detail": "Хранилище PostgreSQL временно недоступно."}


def test_front_report_create_preserves_multipart_contract(front_client, monkeypatch):
    row = _report_row()
    called = {}

    def create(**kwargs):
        called.update(kwargs)
        return row

    monkeypatch.setattr(front_compat._tasks_repo, "create", create)
    monkeypatch.setattr(
        front_compat,
        "storage_dep",
        lambda: SimpleNamespace(increment_inspection_count=lambda _equipment_id: None),
    )
    response = front_client.post(
        "/front/api/reports",
        data={
            "equipment_id": "pump-1",
            "inspection_id": "insp-1",
            "status": "open",
            "comment": "note",
            "payload": '{"defects": []}',
        },
    )

    assert response.status_code == 200
    assert called["equipment_id"] == "pump-1"
    assert called["inspection_id"] == "insp-1"
    assert called["status"] == "open"
    assert called["comment"] == "note"
    assert called["result"] == {"defects": []}
    assert called["photo_url"] is None
    assert called["assignee_id"] is None


def test_flask_storage_unavailable_returns_503(monkeypatch):
    from app import server

    monkeypatch.setattr(server, "get_storage", lambda: None)
    client = server.flask_app.test_client()
    response = client.get("/api/equipment")
    assert response.status_code == 503
    assert response.is_json
    assert "DATABASE_URL" in response.get_json()["detail"]


def test_flask_database_errors_return_503(monkeypatch):
    from app import server

    class UnavailableStorage:
        def get_all_equipment(self):
            raise DatabaseError("catalog unavailable")

    monkeypatch.setattr(server, "get_storage", lambda: UnavailableStorage())
    response = server.flask_app.test_client().get("/api/equipment")
    assert response.status_code == 503
    assert response.is_json


def test_flask_reports_require_separate_tasks_database(monkeypatch):
    from app import server

    class StorageUsingCatalogForTasks:
        tasks = SimpleNamespace(dsn="postgresql://app@db:5432/catalog")

    monkeypatch.setattr(server, "get_storage", lambda: StorageUsingCatalogForTasks())
    monkeypatch.setenv("DATABASE_URL", "postgresql://app@db:5432/catalog")
    monkeypatch.setenv("DATABASE_TASKS_URL", "postgresql://app@db:5432/catalog")
    response = server.flask_app.test_client().get("/api/reports")
    assert response.status_code == 503
    assert "отдельную PostgreSQL БД" in response.get_json()["detail"]
