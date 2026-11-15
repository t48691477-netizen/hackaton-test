"""Контрактные проверки легаси-хранилища отчётов без PostgreSQL."""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas.report import RepairStatus, ReportCreate
from app.routers import reports as reports_router
from app.services.storage import (
    DB_STATUS_TO_LEGACY,
    LEGACY_STATUS_TO_DB,
    StorageService,
)


class FakeCursor:
    def __init__(self, execute):
        self._execute = execute
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self._result = self._execute(query, params or ())

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._result or []


class FakePool:
    def __init__(self, execute):
        self._execute = execute

    def cursor(self, *, commit=False):
        return FakeCursor(self._execute)


def _report_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "equipment_id": "pump-1",
        "inspection_id": "insp-1",
        "status": "open",
        "comment": "",
        "photo_url": "/photos/original.jpg",
        "result": {"defects": [], "expert_opinion": {}},
        "assignee_id": None,
        "assignee_full_name": None,
        "started_at": None,
        "completed_at": None,
        "repair_comment": None,
        "created_at": datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("legacy_status", "db_status"),
    [
        (RepairStatus.PENDING, "open"),
        (RepairStatus.IN_PROGRESS, "in_progress"),
        (RepairStatus.COMPLETED, "closed"),
        (RepairStatus.REJECTED, "rejected"),
    ],
)
def test_legacy_status_mapping_round_trips(legacy_status, db_status):
    assert LEGACY_STATUS_TO_DB[legacy_status] == db_status
    assert DB_STATUS_TO_LEGACY[db_status] == legacy_status

    service = StorageService(pool=object(), tasks_pool=object())
    report = service._task_row_to_report(_report_row(status=db_status), "Насос 1")
    assert report.repair_status == legacy_status


def test_final_photo_url_round_trips_through_result_json():
    report_id = uuid.uuid4()
    equipment_row = {
        "id": "pump-1",
        "name": "Насос 1",
        "serial_number": "SN-1",
        "location": "Цех 1",
        "commissioned_at": None,
        "component_age": "5 лет",
        "last_maintenance_at": None,
        "state": "operational",
        "components_json": "[]",
        "inspection_count": 0,
        "created_at": datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
    }

    def catalog_execute(query, _params):
        if " = ANY(%s)" in query:
            return []
        if "FULL OUTER JOIN promscan.webapp_equipment" in query:
            return equipment_row
        raise AssertionError(f"Unexpected catalog query: {query}")

    class Tasks:
        row = None
        inserted_result_json = None

        def execute(self, query, params):
            if query.lstrip().startswith("INSERT INTO promscan.reports"):
                self.inserted_result_json = params[4]
                result = json.loads(self.inserted_result_json)
                self.row = _report_row(
                    id=report_id,
                    equipment_id=params[0],
                    inspection_id=params[1],
                    comment=params[2],
                    photo_url=params[3],
                    result=result,
                )
                return dict(self.row)
            if "FROM promscan.reports" in query:
                return dict(self.row) if self.row and str(self.row["id"]) == str(params[0]) else None
            raise AssertionError(f"Unexpected tasks query: {query}")

    tasks = Tasks()
    service = StorageService(
        pool=FakePool(catalog_execute), tasks_pool=FakePool(tasks.execute)
    )
    final_photo_url = "/photos/final.jpg"
    report_in = ReportCreate(
        equipment_id="pump-1",
        dispatcher_notes="Осмотр завершён",
        expert_opinion={
            "criticality": "low",
            "probable_cause": "",
            "recommendations": [],
        },
        photo_url="/photos/original.jpg",
        final_photo_url=final_photo_url,
    )

    created = service.create_report(report_in)
    saved_result = json.loads(tasks.inserted_result_json)
    restored = service.get_report(str(report_id))

    assert saved_result["final_photo_url"] == final_photo_url
    assert created.final_photo_url == final_photo_url
    assert restored.final_photo_url == final_photo_url


def test_rejected_status_keeps_dispatcher_notes_and_sets_fallback_reason():
    report_id = uuid.uuid4()
    existing_notes = "Диспетчерская заметка до смены статуса"
    row = _report_row(comment=existing_notes)

    def tasks_execute(query, params):
        nonlocal row
        if "FROM promscan.reports" in query and query.lstrip().startswith("SELECT"):
            return dict(row)
        if "SET assignee_id = %s, assignee_full_name = %s" in query:
            row["assignee_id"], row["assignee_full_name"] = params[:2]
            return None
        if "SET status = 'rejected'" in query:
            assert "comment = COALESCE(%s, comment)" in query
            assert "Отклонено диспетчером (легаси-контракт)" in query
            assert params == (None, None, str(report_id))
            row["status"] = "rejected"
            if params[0] is not None:
                row["comment"] = params[0]
            if params[1] and params[1].strip():
                row["repair_comment"] = params[1].strip()
            elif not row["repair_comment"]:
                row["repair_comment"] = "Отклонено диспетчером (легаси-контракт)"
            return dict(row)
        raise AssertionError(f"Unexpected tasks query: {query}")

    def catalog_execute(query, _params):
        if " = ANY(%s)" in query:
            return [{"id": "pump-1", "name": "Насос 1"}] if "webapp_equipment" in query else []
        if "SELECT name FROM promscan.webapp_equipment" in query:
            return {"name": "Насос 1"}
        if "SELECT name FROM promscan.equipment" in query:
            return None
        raise AssertionError(f"Unexpected catalog query: {query}")

    service = StorageService(
        pool=FakePool(catalog_execute), tasks_pool=FakePool(tasks_execute)
    )

    report = service.update_report_status(str(report_id), RepairStatus.REJECTED)

    assert report.repair_status == RepairStatus.REJECTED
    assert report.dispatcher_notes == existing_notes
    assert row["comment"] == existing_notes
    assert row["repair_comment"] == "Отклонено диспетчером (легаси-контракт)"


def test_rejected_status_saves_supplied_reason_without_dropping_notes():
    report_id = uuid.uuid4()
    reason = "Ложное срабатывание подтверждено повторной проверкой"
    row = _report_row()

    def tasks_execute(query, params):
        nonlocal row
        if query.lstrip().startswith("SELECT"):
            return dict(row)
        if "SET assignee_id = %s, assignee_full_name = %s" in query:
            row["assignee_id"], row["assignee_full_name"] = params[:2]
            return None
        if "SET status = 'rejected'" in query:
            assert params == (reason, reason, str(report_id))
            row.update(status="rejected", comment=reason, repair_comment=reason)
            return dict(row)
        raise AssertionError(f"Unexpected tasks query: {query}")

    def catalog_execute(query, _params):
        if " = ANY(%s)" in query:
            return []
        raise AssertionError(f"Unexpected catalog query: {query}")

    service = StorageService(
        pool=FakePool(catalog_execute), tasks_pool=FakePool(tasks_execute)
    )

    report = service.update_report_status(
        str(report_id), RepairStatus.REJECTED, dispatcher_notes=reason
    )

    assert report.repair_status == RepairStatus.REJECTED
    assert report.dispatcher_notes == reason
    assert row["comment"] == reason
    assert row["repair_comment"] == reason


def test_invalid_uuid_report_id_returns_not_found_without_database_access():
    class NoDatabaseAccess:
        def cursor(self, **_kwargs):
            raise AssertionError("Invalid UUID must be rejected before DB access")

    service = StorageService(pool=NoDatabaseAccess(), tasks_pool=NoDatabaseAccess())
    app = FastAPI()
    app.include_router(reports_router.router)
    app.dependency_overrides[reports_router.require_dispatch] = lambda: None
    app.dependency_overrides[reports_router.storage_dep] = lambda: service

    response = TestClient(app).get("/api/reports/not-a-uuid")

    assert response.status_code == 404
    assert response.json() == {"detail": "Report not found"}
