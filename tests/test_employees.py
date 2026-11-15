"""Unit and route regressions for the authenticated employee directory."""

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth as auth_router
from app.routers import users as users_router
from app.schemas.auth import AuthAccount
from app.schemas.employee import EmployeeResponse
from app.services.auth import ROLE_PERMISSIONS
from app.services.db import DatabaseError
from app.services.employees import EmployeeNotFoundError, EmployeeService


class FakeEmployeesPool:
    def __init__(self, employee_id: UUID, *, exists: bool = True, events=None):
        self.employee_id = employee_id
        self.exists = exists
        self.active = True
        self.events = events if events is not None else []
        self.update_count = 0

    def cursor(self, *, commit=False):
        return FakeEmployeesCursor(self, commit=commit)


class FakeEmployeesCursor:
    def __init__(self, pool: FakeEmployeesPool, *, commit: bool):
        self.pool = pool
        self.commit_requested = commit
        self.result = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc_value, _traceback):
        if self.commit_requested:
            self.pool.events.append(
                "employees.rollback" if exc_type is not None else "employees.commit"
            )
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT id FROM promscan.employees"):
            self.result = {"id": self.pool.employee_id} if self.pool.exists else None
            return
        if normalized.startswith("UPDATE promscan.employees"):
            assert params == (str(self.pool.employee_id),)
            self.pool.active = False
            self.pool.update_count += 1
            return
        if normalized.startswith("SELECT id, full_name, email, role"):
            self.rows = [
                {
                    "id": self.pool.employee_id,
                    "full_name": "Мария Инженерова",
                    "email": "maria@example.test",
                    "role": "engineer",
                }
            ]
            return
        raise AssertionError(f"Unexpected employee SQL: {normalized}")

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class RecordingAuthService:
    def __init__(self, events, *, error: Exception | None = None):
        self.events = events
        self.error = error
        self.employee_ids = []

    def revoke_employee_access(self, employee_id: str) -> None:
        self.events.append("credentials.revoke")
        self.employee_ids.append(employee_id)
        if self.error is not None:
            raise self.error


class RouteEmployeeService:
    def __init__(self, employees=None, *, error: Exception | None = None):
        self.employees = employees or []
        self.error = error
        self.deactivated_ids = []

    def list_active(self):
        if self.error is not None:
            raise self.error
        return self.employees

    def deactivate(self, employee_id):
        if self.error is not None:
            raise self.error
        self.deactivated_ids.append(employee_id)


def _account(role: str) -> AuthAccount:
    return AuthAccount(
        id=str(uuid4()),
        full_name="Администратор",
        email="admin@example.test",
        role=role,
        permissions=ROLE_PERMISSIONS[role],
    )


def _users_app(monkeypatch, service, *, role: str = "admin") -> FastAPI:
    monkeypatch.setattr(users_router, "employee_service", service)
    app = FastAPI()
    app.include_router(users_router.router)
    app.dependency_overrides[auth_router.require_auth] = lambda: (
        "test-session-token",
        _account(role),
    )
    return app


def test_list_active_returns_public_employee_profiles():
    employee_id = uuid4()
    service = EmployeeService(
        employees_pool=FakeEmployeesPool(employee_id),
        auth_service=RecordingAuthService([]),
    )

    result = service.list_active()

    assert result == [
        EmployeeResponse(
            id=employee_id,
            full_name="Мария Инженерова",
            email="maria@example.test",
            role="engineer",
        )
    ]
    assert "key_hash" not in result[0].model_dump()


def test_deactivate_commits_employee_before_revoking_credentials():
    employee_id = uuid4()
    events = []
    auth_service = RecordingAuthService(events)
    service = EmployeeService(
        employees_pool=FakeEmployeesPool(employee_id, events=events),
        auth_service=auth_service,
    )

    service.deactivate(employee_id)

    assert events == ["employees.commit", "credentials.revoke"]
    assert auth_service.employee_ids == [str(employee_id)]


def test_deactivate_is_idempotent_and_repeats_credential_revocation():
    employee_id = uuid4()
    events = []
    employees_pool = FakeEmployeesPool(employee_id, events=events)
    auth_service = RecordingAuthService(events)
    service = EmployeeService(employees_pool, auth_service)

    service.deactivate(employee_id)
    service.deactivate(str(employee_id))

    assert employees_pool.update_count == 2
    assert auth_service.employee_ids == [str(employee_id), str(employee_id)]
    assert events == [
        "employees.commit",
        "credentials.revoke",
        "employees.commit",
        "credentials.revoke",
    ]


def test_deactivate_leaves_employee_inactive_when_credentials_revoke_fails():
    employee_id = uuid4()
    events = []
    employees_pool = FakeEmployeesPool(employee_id, events=events)
    auth_service = RecordingAuthService(
        events, error=DatabaseError("credentials unavailable")
    )
    service = EmployeeService(employees_pool, auth_service)

    with pytest.raises(DatabaseError, match="credentials unavailable"):
        service.deactivate(employee_id)

    assert employees_pool.active is False
    assert events == ["employees.commit", "credentials.revoke"]


def test_deactivate_rejects_invalid_uuid_before_opening_employee_transaction():
    events = []
    service = EmployeeService(
        employees_pool=FakeEmployeesPool(uuid4(), events=events),
        auth_service=RecordingAuthService(events),
    )

    with pytest.raises(ValueError, match="employee_id must be a UUID"):
        service.deactivate("not-a-uuid")

    assert events == []


def test_deactivate_returns_not_found_without_revoking_credentials():
    employee_id = uuid4()
    events = []
    auth_service = RecordingAuthService(events)
    service = EmployeeService(
        employees_pool=FakeEmployeesPool(employee_id, exists=False, events=events),
        auth_service=auth_service,
    )

    with pytest.raises(EmployeeNotFoundError):
        service.deactivate(employee_id)

    assert events == ["employees.rollback"]
    assert auth_service.employee_ids == []


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        ("director", 200),
        ("admin", 200),
        ("dispatcher", 403),
        ("engineer", 403),
    ],
)
def test_users_routes_enforce_users_permission(monkeypatch, role, expected_status):
    service = RouteEmployeeService(employees=[])
    app = _users_app(monkeypatch, service, role=role)

    with TestClient(app) as client:
        response = client.get("/api/users")

    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json() == []
    else:
        assert service.deactivated_ids == []


def test_users_routes_require_bearer_authentication(monkeypatch):
    service = RouteEmployeeService(employees=[])
    monkeypatch.setattr(users_router, "employee_service", service)
    app = FastAPI()
    app.include_router(users_router.router)

    with TestClient(app) as client:
        response = client.get("/api/users")

    assert response.status_code == 401
    assert service.deactivated_ids == []


def test_get_users_returns_active_profiles_without_secrets(monkeypatch):
    employee_id = uuid4()
    employee = EmployeeResponse(
        id=employee_id,
        full_name="Мария Инженерова",
        email="maria@example.test",
        role="engineer",
    )
    app = _users_app(monkeypatch, RouteEmployeeService([employee]))

    with TestClient(app) as client:
        response = client.get("/api/users")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(employee_id),
            "full_name": "Мария Инженерова",
            "email": "maria@example.test",
            "role": "engineer",
        }
    ]
    assert "key_hash" not in response.text
    assert "is_active" not in response.text


def test_delete_user_is_successful_and_idempotent(monkeypatch):
    employee_id = uuid4()
    service = RouteEmployeeService()
    app = _users_app(monkeypatch, service)

    with TestClient(app) as client:
        first = client.delete(f"/api/users/{employee_id}")
        second = client.delete(f"/api/users/{employee_id}")

    assert first.status_code == 204
    assert second.status_code == 204
    assert service.deactivated_ids == [employee_id, employee_id]


def test_delete_user_maps_not_found_and_database_errors(monkeypatch):
    employee_id = uuid4()

    not_found_app = _users_app(
        monkeypatch,
        RouteEmployeeService(error=EmployeeNotFoundError(str(employee_id))),
    )
    with TestClient(not_found_app) as client:
        not_found = client.delete(f"/api/users/{employee_id}")
    assert not_found.status_code == 404
    assert not_found.json() == {"detail": "Сотрудник не найден."}

    database_app = _users_app(
        monkeypatch,
        RouteEmployeeService(error=DatabaseError("database unavailable")),
    )
    with TestClient(database_app) as client:
        unavailable = client.delete(f"/api/users/{employee_id}")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "detail": "Хранилище сотрудников или credentials временно недоступно."
    }


def test_delete_user_rejects_non_uuid_path_parameter(monkeypatch):
    service = RouteEmployeeService()
    app = _users_app(monkeypatch, service)

    with TestClient(app) as client:
        response = client.delete("/api/users/not-a-uuid")

    assert response.status_code == 422
    assert service.deactivated_ids == []


def test_get_users_maps_employee_database_errors_to_503(monkeypatch):
    app = _users_app(
        monkeypatch,
        RouteEmployeeService(error=DatabaseError("employees unavailable")),
    )

    with TestClient(app) as client:
        response = client.get("/api/users")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Хранилище сотрудников временно недоступно."
    }
