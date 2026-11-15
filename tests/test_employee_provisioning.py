"""Provisioning, rotation, and response-safety tests for /api/users."""

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth as auth_router
from app.routers import users as users_router
from app.schemas.auth import AuthAccount
from app.schemas.employee import EmployeeCreateRequest, EmployeeResponse
from app.services.auth import (
    ACCESS_KEY_PATTERN,
    AuthService,
    ROLE_PERMISSIONS,
    RotatedAccessKey,
)
from app.services.db import DatabaseError
from app.services.employees import (
    EmployeeEmailConflictError,
    EmployeeNotFoundError,
    EmployeeRoleForbiddenError,
    EmployeeService,
)
from app.services.mailer import MailDeliveryError


ACCESS_KEY = "B23456789C"


class FakePgError(Exception):
    sqlstate = "23505"


class ProvisioningEmployeesPool:
    def __init__(self, *, employee_id=None, role="engineer", active=True, events=None):
        self.employee_id = employee_id
        self.row = None
        if employee_id is not None:
            self.row = {
                "id": employee_id,
                "full_name": "Мария Инженерова",
                "email": "maria@example.test",
                "role": role,
                "is_active": active,
                "invitation_status": "not_sent",
                "invitation_provider": None,
                "invitation_sent_at": None,
                "invitation_error": None,
            }
        self.events = events if events is not None else []
        self.duplicate = False
        self.fail_invitation_update = False

    def cursor(self, *, commit=False):
        return ProvisioningEmployeesCursor(self, commit=commit)


class ProvisioningEmployeesCursor:
    def __init__(self, pool, *, commit):
        self.pool = pool
        self.commit_requested = commit
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _value, _traceback):
        if self.commit_requested:
            self.pool.events.append("employees.rollback" if exc_type else "employees.commit")
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        if normalized.startswith("INSERT INTO promscan.employees"):
            self.pool.events.append("employees.insert")
            if self.pool.duplicate:
                try:
                    raise FakePgError("duplicate")
                except FakePgError as cause:
                    raise DatabaseError("database operation failed") from cause
            employee_id = uuid4()
            full_name, email, role = params
            self.pool.employee_id = employee_id
            self.pool.row = {
                "id": employee_id,
                "full_name": full_name,
                "email": email,
                "role": role,
                "is_active": True,
                "invitation_status": "not_sent",
                "invitation_provider": None,
                "invitation_sent_at": None,
                "invitation_error": None,
            }
            self.result = {key: self.pool.row[key] for key in ("id", "full_name", "email", "role")}
            return
        if normalized.startswith("SELECT id, full_name, email, role"):
            employee_id = str(params[0])
            row = self.pool.row
            self.result = (
                {key: row[key] for key in ("id", "full_name", "email", "role")}
                if row is not None
                and str(row["id"]) == employee_id
                and row["is_active"]
                else None
            )
            self.pool.events.append("employees.select")
            return
        if normalized.startswith("UPDATE promscan.employees SET invitation_status"):
            self.pool.events.append("employees.invitation")
            if self.pool.fail_invitation_update:
                raise DatabaseError("employee database unavailable")
            status, provider, sent_at, error, employee_id = params
            if self.pool.row and str(self.pool.row["id"]) == employee_id:
                self.pool.row.update(
                    invitation_status=status,
                    invitation_provider=provider,
                    invitation_sent_at=sent_at,
                    invitation_error=error,
                )
            return
        if normalized.startswith("DELETE FROM promscan.employees"):
            self.pool.events.append("employees.delete")
            if self.pool.row and str(self.pool.row["id"]) == params[0]:
                self.pool.row = None
            return
        raise AssertionError(f"Unexpected employee SQL: {normalized}")

    def fetchone(self):
        return self.result


class ProvisioningAuthService:
    def __init__(self, events=None, *, fail_provision=False):
        self.events = events if events is not None else []
        self.fail_provision = fail_provision
        self.revoked = []
        self.provisioned = []
        self.rotations = []
        self.restored = []
        self.generated_key = ACCESS_KEY

    @staticmethod
    def generate_access_key():
        return ACCESS_KEY

    def provision_employee_access(self, employee_id, access_key):
        self.events.append("credentials.insert")
        self.provisioned.append((employee_id, access_key))
        if self.fail_provision:
            raise DatabaseError("credentials unavailable")

    def revoke_employee_access(self, employee_id):
        self.events.append("credentials.delete")
        self.revoked.append(employee_id)

    def rotate_employee_access(self, employee_id):
        self.events.append("credentials.rotate")
        previous_hash = PasswordHasher().hash(ACCESS_KEY, salt=b"p" * 16)
        result = RotatedAccessKey(ACCESS_KEY, previous_hash, "70" * 16)
        self.rotations.append((employee_id, result))
        return result

    def restore_employee_access(self, employee_id, key_hash, key_salt):
        self.events.append("credentials.restore")
        self.restored.append((employee_id, key_hash, key_salt))


class RouteEmployeeService:
    def __init__(self, employees=None, *, error=None, create_result=None, rotate_result=None):
        self.employees = employees or []
        self.error = error
        self.create_result = create_result
        self.rotate_result = rotate_result
        self.deactivated_ids = []
        self.created = []
        self.rotated = []

    def list_active(self):
        if self.error:
            raise self.error
        return self.employees

    def create(self, payload, *, actor_role):
        if self.error:
            raise self.error
        self.created.append((payload, actor_role))
        return self.create_result

    def rotate_access(self, employee_id, *, actor_role):
        if self.error:
            raise self.error
        self.rotated.append((employee_id, actor_role))
        return self.rotate_result

    def deactivate(self, employee_id):
        if self.error:
            raise self.error
        self.deactivated_ids.append(employee_id)


class CaptureCredentialsPool:
    def __init__(self):
        self.values = None

    @contextmanager
    def cursor(self, *, commit=False):
        yield CaptureCredentialsCursor(self)


class CaptureCredentialsCursor:
    def __init__(self, pool):
        self.pool = pool

    def execute(self, query, params=()):
        if "INSERT INTO promscan.access_key_credentials" in query:
            self.pool.values = params
            return
        raise AssertionError(f"Unexpected credentials SQL: {' '.join(query.split())}")


def _account(role):
    return AuthAccount(
        id=str(uuid4()),
        full_name="Администратор",
        email="admin@example.test",
        role=role,
        permissions=ROLE_PERMISSIONS[role],
    )


def _app(monkeypatch, service, *, role="admin"):
    monkeypatch.setattr(users_router, "employee_service", service)
    app = FastAPI()
    app.include_router(users_router.router)
    app.dependency_overrides[auth_router.require_auth] = lambda: (
        "session",
        _account(role),
    )
    return app


def _payload(**overrides):
    return EmployeeCreateRequest(
        full_name=overrides.get("full_name", "  Иван Иванов  "),
        email=overrides.get("email", "  IVAN@Example.Test "),
        role=overrides.get("role", "engineer"),
    )


def test_create_normalizes_fields_and_orders_insert_credential_mail_then_state(monkeypatch):
    monkeypatch.setattr("app.services.mailer.current_provider", lambda: "resend")
    events = []
    employees = ProvisioningEmployeesPool(events=events)
    auth = ProvisioningAuthService(events)

    def send(email, full_name, role, access_key):
        events.append("mail.send")
        assert (email, full_name, role, access_key) == (
            "ivan@example.test",
            "Иван Иванов",
            "engineer",
            ACCESS_KEY,
        )
        return "<message-id>"

    service = EmployeeService(employees, auth, send_access_key=send)
    result = service.create(_payload(), actor_role="admin")

    assert events == [
        "employees.insert",
        "employees.commit",
        "credentials.insert",
        "mail.send",
        "employees.invitation",
        "employees.commit",
    ]
    assert result.account.email == "ivan@example.test"
    assert result.invitation.status == "sent"
    assert result.invitation.provider == "resend"
    assert result.invitation.sent_at.endswith("Z")
    assert "access_key" not in result.model_dump()
    assert "key_hash" not in result.model_dump()


def test_creation_compensates_credential_and_mail_failures():
    mail_events = []
    employees = ProvisioningEmployeesPool(events=mail_events)
    auth = ProvisioningAuthService(mail_events)

    def fail_mail(*_args):
        mail_events.append("mail.send")
        raise MailDeliveryError("mail failed")

    service = EmployeeService(employees, auth, send_access_key=fail_mail)
    with pytest.raises(MailDeliveryError):
        service.create(_payload(), actor_role="admin")

    assert employees.row is None
    assert auth.revoked == [str(employees.employee_id)]
    assert mail_events[-4:] == [
        "mail.send",
        "credentials.delete",
        "employees.delete",
        "employees.commit",
    ]

    employees = ProvisioningEmployeesPool()
    auth = ProvisioningAuthService(fail_provision=True)
    service = EmployeeService(employees, auth, send_access_key=lambda *_args: "unused")
    with pytest.raises(DatabaseError, match="credentials unavailable"):
        service.create(_payload(), actor_role="admin")
    assert employees.row is None
    assert auth.revoked == [str(employees.employee_id)]


def test_creation_maps_unique_email_conflict_and_cleanup_failure():
    employees = ProvisioningEmployeesPool()
    employees.duplicate = True
    auth = ProvisioningAuthService()
    service = EmployeeService(employees, auth, send_access_key=lambda *_args: "unused")
    with pytest.raises(EmployeeEmailConflictError):
        service.create(_payload(), actor_role="admin")
    assert auth.provisioned == []

    employees = ProvisioningEmployeesPool()
    employees.fail_invitation_update = True
    auth = ProvisioningAuthService()
    service = EmployeeService(employees, auth, send_access_key=lambda *_args: "sent")
    with pytest.raises(DatabaseError, match="employee database unavailable"):
        service.create(_payload(), actor_role="admin")
    assert employees.row is None
    assert auth.revoked == [str(employees.employee_id)]


def test_rotation_restores_old_credential_and_records_failed_invitation():
    employee_id = uuid4()
    events = []
    employees = ProvisioningEmployeesPool(employee_id=employee_id, events=events)
    auth = ProvisioningAuthService(events)

    def fail_mail(*_args):
        events.append("mail.send")
        raise MailDeliveryError("mail failed")

    service = EmployeeService(employees, auth, send_access_key=fail_mail)
    with pytest.raises(MailDeliveryError):
        service.rotate_access(employee_id, actor_role="admin")

    assert events == [
        "employees.select",
        "credentials.rotate",
        "mail.send",
        "credentials.restore",
        "employees.invitation",
        "employees.commit",
    ]
    assert auth.restored == [
        (str(employee_id), auth.rotations[0][1].previous_key_hash, "70" * 16)
    ]
    assert employees.row["invitation_status"] == "failed"
    assert employees.row["invitation_error"] == "MailDeliveryError"
    assert ACCESS_KEY not in repr(auth.restored)


def test_successful_rotation_sends_key_and_returns_public_metadata_only():
    employee_id = uuid4()
    events = []
    employees = ProvisioningEmployeesPool(employee_id=employee_id, events=events)
    auth = ProvisioningAuthService(events)

    def send(email, full_name, role, access_key):
        events.append("mail.send")
        assert (email, full_name, role, access_key) == (
            "maria@example.test",
            "Мария Инженерова",
            "engineer",
            ACCESS_KEY,
        )
        return "<message-id>"

    service = EmployeeService(employees, auth, send_access_key=send)
    result = service.rotate_access(employee_id, actor_role="admin")

    assert events == [
        "employees.select",
        "credentials.rotate",
        "mail.send",
        "employees.invitation",
        "employees.commit",
    ]
    assert result.invitation.status == "sent"
    assert ACCESS_KEY not in repr(result.model_dump())
    assert all(
        secret not in repr(result.model_dump())
        for secret in ("key_hash", "key_salt", "is_active")
    )


@pytest.mark.parametrize("actor_role", ["admin", "dispatcher", "engineer"])
def test_only_director_can_create_admin(actor_role):
    employees = ProvisioningEmployeesPool()
    auth = ProvisioningAuthService()
    service = EmployeeService(employees, auth, send_access_key=lambda *_args: "unused")

    with pytest.raises(EmployeeRoleForbiddenError):
        service.create(_payload(role="admin"), actor_role=actor_role)
    assert employees.row is None
    assert auth.provisioned == []


def test_rotation_rejects_inactive_employee_without_touching_credentials():
    employees = ProvisioningEmployeesPool(employee_id=uuid4(), active=False)
    auth = ProvisioningAuthService()
    service = EmployeeService(employees, auth, send_access_key=lambda *_args: "unused")

    with pytest.raises(EmployeeNotFoundError):
        service.rotate_access(employees.employee_id, actor_role="director")
    assert auth.rotations == []


def test_auth_service_provisions_argon2id_hash_with_explicit_salt():
    pool = CaptureCredentialsPool()
    service = AuthService(pool=pool)
    service.provision_employee_access(str(uuid4()), ACCESS_KEY)

    employee_id, key_hash, key_salt = pool.values
    assert employee_id
    assert key_hash.startswith("$argon2id$")
    assert len(key_salt) == 32
    assert all(character in "0123456789abcdef" for character in key_salt)
    assert AuthService._encoded_salt_hex(key_hash) == key_salt
    assert PasswordHasher().verify(key_hash, ACCESS_KEY)
    assert ACCESS_KEY not in key_hash


def test_generated_keys_match_the_login_alphabet():
    for _ in range(20):
        assert ACCESS_KEY_PATTERN.fullmatch(AuthService.generate_access_key())


def test_create_route_returns_public_response_only(monkeypatch):
    employee_id = uuid4()
    account = EmployeeResponse(
        id=employee_id,
        full_name="Иван Иванов",
        email="ivan@example.test",
        role="engineer",
    )
    service = RouteEmployeeService(
        create_result={
            "account": account,
            "invitation": {
                "status": "sent",
                "provider": "resend",
                "email": account.email,
                "sent_at": "2026-11-15T10:30:00Z",
            },
        }
    )
    app = _app(monkeypatch, service)

    with TestClient(app) as client:
        response = client.post(
            "/api/users",
            json={"full_name": "Иван Иванов", "email": "IVAN@example.test", "role": "engineer"},
        )

    assert response.status_code == 201
    assert response.json()["account"]["id"] == str(employee_id)
    assert response.json()["invitation"]["status"] == "sent"
    assert all(secret not in response.text for secret in (ACCESS_KEY, "key_hash", "key_salt", "is_active"))
    assert service.created[0][1] == "admin"
    assert service.created[0][0].email == "ivan@example.test"


@pytest.mark.parametrize("role", ["dispatcher", "engineer"])
def test_create_and_rotation_routes_require_users_permission(monkeypatch, role):
    employee_id = uuid4()
    service = RouteEmployeeService()
    app = _app(monkeypatch, service, role=role)
    payload = {"full_name": "Иван Иванов", "email": "ivan@example.test", "role": "engineer"}

    with TestClient(app) as client:
        created = client.post("/api/users", json=payload)
        rotated = client.post(f"/api/users/{employee_id}/access")

    assert created.status_code == 403
    assert rotated.status_code == 403
    assert service.created == []
    assert service.rotated == []


def test_create_route_maps_duplicate_mail_and_role_errors_safely(monkeypatch):
    payload = {"full_name": "Иван Иванов", "email": "ivan@example.test", "role": "engineer"}

    cases = [
        (EmployeeEmailConflictError("private@example.test"), 409),
        (EmployeeRoleForbiddenError("private role info"), 403),
        (MailDeliveryError(f"failed key {ACCESS_KEY}"), 502),
        (DatabaseError(f"database error containing {ACCESS_KEY}"), 503),
    ]
    for error, expected in cases:
        app = _app(monkeypatch, RouteEmployeeService(error=error))
        with TestClient(app) as client:
            response = client.post("/api/users", json=payload)
        assert response.status_code == expected
        assert ACCESS_KEY not in response.text
        assert "private@example.test" not in response.text
        assert "private role info" not in response.text


def test_rotation_route_maps_inactive_and_returns_no_access_key(monkeypatch):
    employee_id = uuid4()
    account = EmployeeResponse(
        id=employee_id,
        full_name="Иван Иванов",
        email="ivan@example.test",
        role="engineer",
    )
    service = RouteEmployeeService(
        rotate_result={
            "account": account,
            "invitation": {
                "status": "sent",
                "provider": "resend",
                "email": account.email,
                "sent_at": "2026-11-15T10:30:00Z",
            },
        }
    )
    app = _app(monkeypatch, service)
    with TestClient(app) as client:
        response = client.post(f"/api/users/{employee_id}/access")
    assert response.status_code == 200
    assert response.json()["account"]["id"] == str(employee_id)
    assert service.rotated == [(employee_id, "admin")]
    assert all(secret not in response.text for secret in (ACCESS_KEY, "key_hash", "key_salt"))

    missing = _app(monkeypatch, RouteEmployeeService(error=EmployeeNotFoundError("secret")))
    with TestClient(missing) as client:
        response = client.post(f"/api/users/{employee_id}/access")
    assert response.status_code == 404
    assert "secret" not in response.text


def test_create_request_rejects_extra_fields_bad_email_and_director_role():
    common = {"full_name": "Иван Иванов", "email": "ivan@example.test"}
    for invalid in (
        {**common, "role": "engineer", "access_key": ACCESS_KEY},
        {**common, "role": "engineer", "email": "bad"},
        {**common, "role": "director"},
    ):
        with pytest.raises(ValueError):
            EmployeeCreateRequest(**invalid)
