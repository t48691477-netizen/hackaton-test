import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import uuid

import app.services.auth as auth_module
from app.schemas.auth import AuthAccount
from app.services.auth import (
    AuthService,
    LoginReservation,
    VerifiedAccount,
    LOGIN_FAILURE_LIMIT,
    LOGIN_WINDOW,
)
from app.services.db import DatabaseError


class UnavailablePool:
    @contextmanager
    def cursor(self, *, commit=False):
        raise DatabaseError("test database unavailable")
        yield


class LoginAttemptsPool:
    """Минимальный fake credentials pool для проверки SQL rate-limit ветки."""

    def __init__(self, attempts=None):
        self.attempts = list(attempts or [])
        self.next_id = len(self.attempts) + 1

    def cursor(self, *, commit=False):
        return _LoginAttemptsCursor(self)


class _LoginAttemptsCursor:
    def __init__(self, pool):
        self.pool = pool
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT pg_advisory_xact_lock"):
            return
        if normalized.startswith("DELETE FROM promscan.auth_login_attempts"):
            identifier_fp, source_fp, cutoff = params
            self.pool.attempts = [
                attempt
                for attempt in self.pool.attempts
                if not (
                    (
                        attempt["identifier_fingerprint"] == identifier_fp
                        or attempt["source_fingerprint"] == source_fp
                    )
                    and attempt["attempted_at"] < cutoff
                )
            ]
            return
        if "FROM promscan.auth_login_attempts" in normalized and "identifier_fingerprint = %s" in normalized:
            identifier_fp, cutoff = params
            self.result = {
                "failures": sum(
                    attempt["identifier_fingerprint"] == identifier_fp
                    and not attempt["was_successful"]
                    and attempt["attempted_at"] > cutoff
                    for attempt in self.pool.attempts
                )
            }
            return
        if "FROM promscan.auth_login_attempts" in normalized and "source_fingerprint = %s" in normalized:
            source_fp, cutoff = params
            self.result = {
                "failures": sum(
                    attempt["source_fingerprint"] == source_fp
                    and not attempt["was_successful"]
                    and attempt["attempted_at"] > cutoff
                    for attempt in self.pool.attempts
                )
            }
            return
        if normalized.startswith("INSERT INTO promscan.auth_login_attempts"):
            identifier_fp, source_fp = params
            attempt_id = self.pool.next_id
            self.pool.next_id += 1
            self.pool.attempts.append(
                {
                    "id": attempt_id,
                    "identifier_fingerprint": identifier_fp,
                    "source_fingerprint": source_fp,
                    "was_successful": False,
                    "attempted_at": datetime.now(timezone.utc),
                }
            )
            self.result = {"id": attempt_id}
            return
        raise AssertionError(f"Unexpected auth SQL: {normalized}")

    def fetchone(self):
        return self.result


class SessionCapturePool:
    def __init__(self):
        self.session_employee_id = None
        self.queries = []

    def cursor(self, *, commit=False):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        self.queries.append(normalized)
        if "INSERT INTO promscan.auth_sessions" in normalized:
            self.session_employee_id = params[0]
            return
        if "access_key_credentials" in normalized:
            raise AssertionError("provisioned accounts must not use the legacy credential path")
        raise AssertionError(f"Unexpected session SQL: {normalized}")


class AccountLookupPool:
    def __init__(self, credential=None, employee=None):
        self.credential = credential
        self.employee = employee

    def cursor(self, *, commit=False):
        return _AccountLookupCursor(self)


class _AccountLookupCursor:
    def __init__(self, pool):
        self.pool = pool
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT employee_id, key_hash, key_salt"):
            self.rows = [self.pool.credential] if self.pool.credential else []
        elif normalized.startswith("SELECT id, full_name, email, role"):
            self.result = self.pool.employee
        else:
            raise AssertionError(f"Unexpected account lookup SQL: {normalized}")

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.result


def test_concurrent_attempt_reservation_is_atomic(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    service = AuthService(pool=UnavailablePool())
    barrier = threading.Barrier(LOGIN_FAILURE_LIMIT + 3)

    def attempt(_):
        barrier.wait()
        return service.reserve_login_attempt("B23456789C", "203.0.113.9")

    with ThreadPoolExecutor(max_workers=LOGIN_FAILURE_LIMIT + 3) as pool:
        results = list(pool.map(attempt, range(LOGIN_FAILURE_LIMIT + 3)))

    assert sum(result is not None for result in results) == LOGIN_FAILURE_LIMIT
    assert sum(result is None for result in results) == 3


def test_attempt_reservation_limits_both_key_and_source(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    service = AuthService(pool=UnavailablePool())

    for _ in range(LOGIN_FAILURE_LIMIT):
        assert service.reserve_login_attempt("B23456789C", "203.0.113.9") is not None
    assert service.reserve_login_attempt("B23456789C", "203.0.113.10") is None
    assert service.reserve_login_attempt("C23456789D", "203.0.113.9") is None


def test_postgres_reservation_counts_identifier_and_source_independently(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    service = AuthService(pool=LoginAttemptsPool())
    now = service._now()
    identifier_fp = service._fp("identifier", "B23456789C")
    source_fp = service._fp("source", "203.0.113.9")
    attempts = []

    # Три ошибки того же ключа с другими источниками.
    for index in range(3):
        attempts.append(
            {
                "identifier_fingerprint": identifier_fp,
                "source_fingerprint": service._fp("source", f"198.51.100.{index}"),
                "was_successful": False,
                "attempted_at": now,
            }
        )
    # Две ошибки того же источника с другими ключами. Старый OR-запрос
    # сложил бы их в пять и ошибочно заблокировал бы следующую попытку.
    for index in range(2):
        attempts.append(
            {
                "identifier_fingerprint": service._fp("identifier", f"other-{index}"),
                "source_fingerprint": source_fp,
                "was_successful": False,
                "attempted_at": now,
            }
        )
    pool = LoginAttemptsPool(attempts)
    service = AuthService(pool=pool)

    assert service.reserve_login_attempt("B23456789C", "203.0.113.9") is not None


def test_memory_fallback_prunes_expired_keys_and_has_a_bound(monkeypatch):
    monkeypatch.setattr(auth_module, "LOGIN_MEMORY_MAX_KEYS", 4)
    service = AuthService(pool=UnavailablePool())
    now = service._now()
    service._mem_attempts["stale"] = [
        (now - LOGIN_WINDOW - timedelta(seconds=1), "expired")
    ]
    service._mem_lockout["stale"] = now - timedelta(seconds=1)

    for index in range(12):
        identifier_fp = bytes([index]) * 32
        source_fp = bytes([index + 100]) * 32
        assert service._mem_reserve(identifier_fp, source_fp, now) is not None

    assert "stale" not in service._mem_attempts
    assert "stale" not in service._mem_lockout
    assert len(service._mem_attempts) <= 4
    assert len(service._mem_lockout) <= 4


def test_provisioned_account_does_not_use_legacy_account_uuid(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    monkeypatch.setenv("TOIR_ACCESS_KEY_HASH", "configured-legacy-hash")
    monkeypatch.setenv("TOIR_ACCOUNT_ID", "legacy-account")
    pool = SessionCapturePool()
    service = AuthService(pool=pool, employees_pool=pool)
    employee_id = str(uuid.uuid4())
    account = AuthAccount(
        id=employee_id,
        full_name="Provisioned Engineer",
        email="engineer@example.test",
        role="engineer",
        permissions=["scan"],
    )
    monkeypatch.setattr(
        service,
        "_verify_key_with_source",
        lambda _access_key: VerifiedAccount(account=account, is_legacy=False),
    )
    access_key = "B23456789C"
    source_id = "203.0.113.9"
    reservation = LoginReservation(
        service._fp("identifier", access_key),
        service._fp("source", source_id),
    )

    response = service.login_reserved(access_key, source_id, reservation)

    assert response is not None
    assert response.account.id == employee_id
    assert pool.session_employee_id == employee_id
    assert not any("access_key_credentials" in query for query in pool.queries)


def test_provisioned_credential_can_use_legacy_configured_uuid(monkeypatch):
    legacy_employee_id = str(uuid.uuid4())
    monkeypatch.setenv("TOIR_ACCOUNT_ID", legacy_employee_id)
    provisioned_key = "C23456789D"
    legacy_key = "B23456789C"
    provisioned_hash = AuthService()._ph.hash(provisioned_key)
    legacy_hash = AuthService()._ph.hash(legacy_key)
    monkeypatch.setenv("TOIR_ACCESS_KEY_HASH", legacy_hash)
    employee_id = uuid.UUID(legacy_employee_id)
    credential = {
        "employee_id": employee_id,
        "key_hash": provisioned_hash,
        "key_salt": AuthService._encoded_salt_hex(provisioned_hash),
    }
    employee = {
        "id": employee_id,
        "full_name": "Provisioned Employee",
        "email": "provisioned@example.test",
        "role": "engineer",
    }
    service = AuthService(
        pool=AccountLookupPool(credential=credential, employee=employee),
        employees_pool=AccountLookupPool(credential=credential, employee=employee),
    )

    verified = service._verify_key_with_source(provisioned_key)

    assert verified is not None
    assert verified.is_legacy is False
    assert verified.account.id == str(employee_id)


def test_expired_memory_attempts_are_pruned(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    service = AuthService(pool=UnavailablePool())
    now = service._now()
    identifier_fp = service._fp("identifier", "B23456789C")
    source_fp = service._fp("source", "203.0.113.9")

    for _ in range(LOGIN_FAILURE_LIMIT):
        assert service._mem_reserve(identifier_fp, source_fp, now) is not None
    assert service._mem_reserve(identifier_fp, source_fp, now) is None
    assert service._mem_reserve(
        identifier_fp, source_fp, now + LOGIN_WINDOW + timedelta(seconds=1)
    ) is not None


def test_success_marks_only_its_reserved_attempt(monkeypatch):
    monkeypatch.setenv("LOGIN_FP_SECRET", "unit-test-secret")
    service = AuthService(pool=UnavailablePool())
    now = service._now()
    reservations = [
        service._mem_reserve(
            service._fp("identifier", "B23456789C"),
            service._fp("source", "203.0.113.9"),
            now,
        )
        for _ in range(LOGIN_FAILURE_LIMIT)
    ]
    assert all(reservation is not None for reservation in reservations)

    service.mark_login_success(reservations[1])

    expected_remaining = {
        reservation.memory_nonce
        for index, reservation in enumerate(reservations)
        if index != 1
    }
    identifier_key = reservations[0].identifier_fingerprint.hex()
    source_key = reservations[0].source_fingerprint.hex()
    assert {nonce for _, nonce in service._mem_attempts[identifier_key]} == expected_remaining
    assert {nonce for _, nonce in service._mem_attempts[source_key]} == expected_remaining
    assert service.reserve_login_attempt("B23456789C", "203.0.113.9") is not None
    assert service.reserve_login_attempt("B23456789C", "203.0.113.9") is None
