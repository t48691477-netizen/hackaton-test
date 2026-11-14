from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.routers import reports as reports_router
from app.routers.auth import require_dispatch, require_scan
from app.services.storage import StorageService


@pytest.fixture
def report_api(tmp_path, monkeypatch):
    db_path = tmp_path / "reports.sqlite3"
    storage = StorageService(db_path)
    monkeypatch.setattr(reports_router, "storage_service", storage)
    app = FastAPI()
    app.include_router(reports_router.router)
    app.dependency_overrides[reports_router.require_scan] = lambda: object()
    app.dependency_overrides[reports_router.require_dispatch] = lambda: object()
    return TestClient(app), db_path


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
    assert client.get(f"/api/reports/{first_report['id']}").json() == first_report


def test_status_transitions_persist_timestamps_and_notes(report_api):
    client, db_path = report_api
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

    persisted = StorageService(db_path).get_report(created["id"])
    assert persisted is not None
    assert persisted.repair_status.value == "completed"
    assert persisted.completed_at == completed_report["completed_at"]
    assert persisted.dispatcher_notes == "Crew assigned"


@pytest.mark.parametrize(
    ("initial_status", "new_status"),
    [
        ("pending", "completed"),
        ("in_progress", "pending"),
        ("completed", "rejected"),
        ("rejected", "in_progress"),
    ],
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


def test_existing_reports_table_is_migrated(tmp_path):
    import sqlite3

    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE reports (
                id TEXT PRIMARY KEY, equipment_id TEXT NOT NULL,
                equipment_name TEXT NOT NULL, created_at TEXT NOT NULL,
                repair_status TEXT NOT NULL, dispatcher_notes TEXT,
                defects_count INTEGER NOT NULL, defects_json TEXT NOT NULL,
                expert_opinion_json TEXT NOT NULL, photo_url TEXT NOT NULL,
                final_photo_url TEXT
            )
        """)

    storage = StorageService(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
    assert {"started_at", "completed_at", "updated_at"} <= columns
    assert storage.get_reports() == []
