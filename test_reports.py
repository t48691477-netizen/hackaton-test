import os
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.routers import reports as reports_router
from app.services.db import PostgresPool
from app.services.storage import StorageService


PROJECT_ROOT = Path(__file__).resolve().parent
TASKS_SCHEMA = PROJECT_ROOT / "database" / "sql" / "tasks" / "001_schema.sql"
TASKS_REJECTED_MIGRATION = (
    PROJECT_ROOT / "database" / "sql" / "tasks" / "002_rejected_status.sql"
)
CATALOG_SCHEMA = PROJECT_ROOT / "database" / "migrations" / "001_core.sql"
WEBAPP_CATALOG_MIGRATION = (
    PROJECT_ROOT / "database" / "migrations" / "005_webapp_catalog.sql"
)


@pytest.fixture(scope="session")
def report_test_dsns():
    tasks_dsn = os.getenv("DATABASE_TEST_TASKS_URL", "").strip()
    catalog_dsn = os.getenv("DATABASE_TEST_CATALOG_URL", "").strip()
    if not tasks_dsn or not catalog_dsn:
        missing = [
            name
            for name, value in (
                ("DATABASE_TEST_TASKS_URL", tasks_dsn),
                ("DATABASE_TEST_CATALOG_URL", catalog_dsn),
            )
            if not value
        ]
        pytest.skip(f"Не заданы {', '.join(missing)}; PostgreSQL API-тесты пропущены")

    production_dsns = {
        os.getenv(name, "").strip()
        for name in ("DATABASE_URL", "DATABASE_CATALOG_URL", "DATABASE_TASKS_URL")
    }
    for env_name, dsn in (
        ("DATABASE_TEST_TASKS_URL", tasks_dsn),
        ("DATABASE_TEST_CATALOG_URL", catalog_dsn),
    ):
        if dsn in production_dsns:
            pytest.fail(f"{env_name} совпадает с production DSN; тесты остановлены")
    return tasks_dsn, catalog_dsn


@pytest.fixture(scope="session")
def report_test_databases(report_test_dsns):
    psycopg = pytest.importorskip(
        "psycopg", reason="Для PostgreSQL API-тестов нужен psycopg >= 3.2"
    )
    version = tuple(int(part) for part in psycopg.__version__.split(".")[:2])
    if version < (3, 2):
        pytest.skip(f"Для PostgreSQL API-тестов нужен psycopg >= 3.2, найден {psycopg.__version__}")

    tasks_source_dsn, catalog_source_dsn = report_test_dsns
    suffix = uuid.uuid4().hex[:10]
    databases = []

    def create_database(source_dsn, name):
        params = psycopg.conninfo.conninfo_to_dict(source_dsn)
        admin_params = dict(params, dbname="postgres")
        admin_dsn = psycopg.conninfo.make_conninfo(**admin_params)
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(
                psycopg.sql.SQL("CREATE DATABASE {}").format(
                    psycopg.sql.Identifier(name)
                )
            )
        test_params = dict(params, dbname=name)
        return psycopg.conninfo.make_conninfo(**test_params), admin_dsn, name

    try:
        tasks_dsn, tasks_admin_dsn, tasks_name = create_database(
            tasks_source_dsn, f"promscan_reports_api_tasks_pytest_{suffix}"
        )
        databases.append((tasks_admin_dsn, tasks_name))
        catalog_dsn, catalog_admin_dsn, catalog_name = create_database(
            catalog_source_dsn, f"promscan_reports_api_catalog_pytest_{suffix}"
        )
        databases.append((catalog_admin_dsn, catalog_name))

        for path in (TASKS_SCHEMA, TASKS_REJECTED_MIGRATION):
            if path.exists():
                with psycopg.connect(tasks_dsn, autocommit=True) as connection:
                    connection.execute(path.read_text(encoding="utf-8"))
        for path in (CATALOG_SCHEMA, WEBAPP_CATALOG_MIGRATION):
            with psycopg.connect(catalog_dsn, autocommit=True) as connection:
                connection.execute(path.read_text(encoding="utf-8"))
        with psycopg.connect(catalog_dsn) as connection:
            connection.execute(
                """
                INSERT INTO promscan.webapp_equipment (id, name)
                VALUES ('pump_d1250_03', 'Test pump')
                """
            )
        yield catalog_dsn, tasks_dsn
    finally:
        for admin_dsn, name in reversed(databases):
            with psycopg.connect(admin_dsn, autocommit=True) as connection:
                try:
                    connection.execute(
                        psycopg.sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                            psycopg.sql.Identifier(name)
                        )
                    )
                except psycopg.errors.SyntaxError:
                    connection.execute(
                        psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                            psycopg.sql.Identifier(name)
                        )
                    )


@pytest.fixture
def report_api(report_test_databases):
    catalog_dsn, tasks_dsn = report_test_databases
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(tasks_dsn, autocommit=True) as connection:
        connection.execute("TRUNCATE TABLE promscan.reports")
    with psycopg.connect(catalog_dsn, autocommit=True) as connection:
        connection.execute(
            "TRUNCATE TABLE promscan.webapp_equipment RESTART IDENTITY CASCADE"
        )
        connection.execute(
            """
            INSERT INTO promscan.webapp_equipment (id, name)
            VALUES ('pump_d1250_03', 'Test pump')
            """
        )

    catalog_pool = PostgresPool(catalog_dsn, name="test catalog")
    tasks_pool = PostgresPool(tasks_dsn, name="test tasks")
    storage = StorageService(pool=catalog_pool, tasks_pool=tasks_pool)
    app = FastAPI()
    app.include_router(reports_router.router)
    app.dependency_overrides[reports_router.require_scan] = lambda: object()
    app.dependency_overrides[reports_router.require_dispatch] = lambda: object()
    app.dependency_overrides[reports_router.storage_dep] = lambda: storage
    try:
        yield TestClient(app), storage
    finally:
        catalog_pool.close()
        tasks_pool.close()


def report_payload(equipment_id="pump_d1250_03"):
    return {
        "equipment_id": equipment_id,
        "repair_status": "pending",
        "dispatcher_notes": "",
        "defects": [],
        "expert_opinion": {
            "criticality": "low",
            "probable_cause": "Routine inspection",
            "recommendations": ["Monitor equipment"],
        },
        "photo_url": "/static/uploads/test.jpg",
        "final_photo_url": None,
    }


def test_create_read_and_unique_ids_keep_existing_contract(report_api):
    client, _ = report_api
    first = client.post("/api/reports", json=report_payload())
    second = client.post("/api/reports", json=report_payload())

    assert first.status_code == second.status_code == 201
    first_report, second_report = first.json(), second.json()
    assert first_report["id"] != second_report["id"]
    assert first_report["repair_status"] == "pending"
    assert first_report["started_at"] is None
    assert first_report["completed_at"] is None
    assert first_report["updated_at"] == first_report["created_at"]
    assert {
        "id", "equipment_id", "equipment_name", "created_at", "repair_status",
        "dispatcher_notes", "defects_count", "defects", "expert_opinion",
        "photo_url", "final_photo_url",
    } <= first_report.keys()
    assert first_report["equipment_name"] == "Test pump"
    assert client.get(f"/api/reports/{first_report['id']}").json() == first_report


def test_status_transitions_persist_timestamps_and_notes(report_api):
    client, storage = report_api
    created = client.post("/api/reports", json=report_payload()).json()

    started = client.patch(
        f"/api/reports/{created['id']}/status",
        json={"status": "in_progress", "dispatcher_notes": "Crew assigned"},
    )
    assert started.status_code == 200
    started_report = started.json()
    assert started_report["repair_status"] == "in_progress"
    assert started_report["dispatcher_notes"] == "Crew assigned"
    assert started_report["started_at"]
    assert started_report["completed_at"] is None

    repeated = client.patch(
        f"/api/reports/{created['id']}/status", json={"status": "in_progress"}
    )
    assert repeated.status_code == 200
    assert repeated.json()["started_at"] == started_report["started_at"]
    assert repeated.json()["updated_at"] == started_report["updated_at"]

    completed = client.patch(
        f"/api/reports/{created['id']}/status", json={"status": "completed"}
    )
    assert completed.status_code == 200
    completed_report = completed.json()
    assert completed_report["completed_at"]
    assert completed_report["started_at"] == started_report["started_at"]

    persisted = storage.get_report(created["id"])
    assert persisted is not None
    assert persisted.repair_status.value == "completed"
    assert persisted.completed_at == completed_report["completed_at"]
    assert persisted.dispatcher_notes == "Crew assigned"


def test_pending_can_be_completed_directly_via_legacy_contract(report_api):
    client, _ = report_api
    created = client.post("/api/reports", json=report_payload()).json()

    response = client.patch(
        f"/api/reports/{created['id']}/status", json={"status": "completed"}
    )

    assert response.status_code == 200
    completed = response.json()
    assert completed["repair_status"] == "completed"
    assert completed["started_at"]
    assert completed["completed_at"]


@pytest.mark.parametrize(
    ("initial_status", "new_status"),
    [("in_progress", "pending"), ("completed", "rejected"), ("rejected", "in_progress")],
)
def test_invalid_status_transitions_return_conflict(report_api, initial_status, new_status):
    client, _ = report_api
    payload = report_payload()
    payload["repair_status"] = initial_status
    created = client.post("/api/reports", json=payload).json()

    response = client.patch(
        f"/api/reports/{created['id']}/status", json={"status": new_status}
    )
    assert response.status_code == 409
    assert client.get(f"/api/reports/{created['id']}").json()["repair_status"] == initial_status


@pytest.mark.parametrize("initial_status", ["pending", "in_progress"])
def test_rejected_is_allowed_from_pending_or_in_progress(report_api, initial_status):
    client, _ = report_api
    payload = report_payload()
    payload["repair_status"] = initial_status
    created = client.post("/api/reports", json=payload).json()

    response = client.patch(
        f"/api/reports/{created['id']}/status", json={"status": "rejected"}
    )
    assert response.status_code == 200
    assert response.json()["repair_status"] == "rejected"


def test_unknown_report_and_equipment_return_not_found(report_api):
    client, _ = report_api
    assert client.get("/api/reports/missing").status_code == 404
    assert client.patch(
        "/api/reports/missing/status", json={"status": "in_progress"}
    ).status_code == 404
    assert client.post("/api/reports", json=report_payload("missing")).status_code == 404
