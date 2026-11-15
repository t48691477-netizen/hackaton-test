"""Сервис аутентификации на PostgreSQL (база credentials + employees).

Схемы: database/sql/credentials/001_schema.sql (+002, 003) и
database/sql/employees/001_schema.sql.

Легаси-режим одного ключа из TOIR_ACCESS_KEY_HASH сохранён как fallback,
когда в promscan.access_key_credentials нет записей: это позволяет
разворачивать приложение до выдачи ключей сотрудникам. Сессии при этом
всё равно хранятся в PostgreSQL.
"""

import hashlib
import hmac
import os
import secrets
import threading
import base64
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.schemas.auth import AuthAccount, AuthLoginResponse, Permission, Role
from app.services.db import (
    DatabaseError,
    DatabaseNotConfigured,
    PostgresPool,
    pools,
)


SESSION_TTL = timedelta(hours=8)
LOGIN_WINDOW = timedelta(minutes=10)
LOGIN_LOCKOUT = timedelta(minutes=10)
LOGIN_FAILURE_LIMIT = 5
# Аварийное состояние используется только при недоступности PostgreSQL.
# Ограничение не даёт разнообразным fingerprint-ам расти без bounds.
LOGIN_MEMORY_MAX_KEYS = 10_000
ACCESS_KEY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ACCESS_KEY_LENGTH = 10
KEY_SALT_BYTES = 16
ACCESS_KEY_PATTERN = re.compile(r"^[A-HJ-NP-Z2-9]{10}$")
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    "director": ["scan", "dispatch", "users"],
    "admin": ["scan", "dispatch", "users"],
    "dispatcher": ["scan", "dispatch"],
    "engineer": ["scan"],
}


class AuthConfigurationError(Exception):
    pass


@dataclass(frozen=True)
class LoginReservation:
    identifier_fingerprint: bytes
    source_fingerprint: bytes
    attempt_id: Optional[int] = None
    memory_nonce: Optional[str] = None


@dataclass(frozen=True)
class VerifiedAccount:
    account: AuthAccount
    is_legacy: bool


@dataclass(frozen=True)
class RotatedAccessKey:
    """Internal key-rotation result; never serialize this object in an API."""

    access_key: str
    previous_key_hash: str
    previous_key_salt: str


class AuthService:
    def __init__(self, pool: Optional[PostgresPool] = None, employees_pool: Optional[PostgresPool] = None):
        self._pool = pool
        self._employees_pool = employees_pool
        self._ph = PasswordHasher()
        self._lock = threading.Lock()
        # Резервные счётчики для случая недоступной БД: лимит входа
        # не должен молча исчезать при сбое PostgreSQL.
        self._mem_attempts: dict[str, list[tuple[datetime, str]]] = {}
        self._mem_lockout: dict[str, datetime] = {}

    @property
    def pool(self) -> PostgresPool:
        if self._pool is None:
            self._pool = pools.get("credentials")
        return self._pool

    @property
    def employees_pool(self) -> PostgresPool:
        if self._employees_pool is None:
            self._employees_pool = pools.get("employees")
        return self._employees_pool

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _token_hash(token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    # ------------------------------------------------------------------
    # Валидация ключа
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_encoded(encoded_hash: str, access_key: str) -> bool:
        if not encoded_hash.startswith("$argon2id$"):
            raise AuthConfigurationError(
                "TOIR_ACCESS_KEY_HASH must contain an Argon2id hash"
            )
        try:
            if not PasswordHasher().verify(encoded_hash, access_key):
                return False
            if PasswordHasher().check_needs_rehash(encoded_hash):
                raise AuthConfigurationError(
                    "TOIR_ACCESS_KEY_HASH must use current Argon2id parameters"
                )
            return True
        except VerifyMismatchError:
            return False
        except AuthConfigurationError:
            raise
        except Exception as exc:
            raise AuthConfigurationError("TOIR_ACCESS_KEY_HASH is invalid") from exc

    def _verify_key(self, access_key: str) -> Optional[AuthAccount]:
        """Возвращает профиль для совместимости с внутренними callers."""
        verified = self._verify_key_with_source(access_key)
        return verified.account if verified is not None else None

    def _verify_key_with_source(self, access_key: str) -> Optional[VerifiedAccount]:
        """Проверяет ключ в credentials-БД и отдельно читает профиль сотрудника."""
        try:
            with self.pool.cursor() as cur:
                cur.execute(
                    """
                    SELECT employee_id, key_hash, key_salt
                    FROM promscan.access_key_credentials
                    """
                )
                rows = cur.fetchall()
        except DatabaseError:
            raise
        for row in rows or []:
            if not self._verify_encoded(row["key_hash"], access_key):
                continue
            stored_salt = row.get("key_salt")
            if not stored_salt:
                raise AuthConfigurationError(
                    "Credential key_salt is missing; reissue or backfill the key"
                )
            if self._encoded_salt_hex(row["key_hash"]) != stored_salt:
                raise AuthConfigurationError("Credential key_salt does not match its PHC hash")
            legacy_uuid = self._legacy_account_uuid()
            env_hash = os.environ.get("TOIR_ACCESS_KEY_HASH", "")
            if (
                legacy_uuid
                and str(row["employee_id"]) == legacy_uuid
                and env_hash
                and hmac.compare_digest(row["key_hash"], env_hash)
                and self._legacy_account_is_active()
            ):
                return VerifiedAccount(self._env_account(), is_legacy=True)
            with self.employees_pool.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, full_name, email, role
                    FROM promscan.employees
                    WHERE id = %s AND is_active
                    """,
                    (row["employee_id"],),
                )
                employee = cur.fetchone()
            if employee is None:
                continue
            return VerifiedAccount(
                AuthAccount(
                    id=str(employee["id"]),
                    full_name=employee["full_name"],
                    email=employee["email"],
                    role=employee["role"],
                    permissions=ROLE_PERMISSIONS.get(employee["role"], ["scan"]),
                ),
                is_legacy=False,
            )
        # Legacy fallback is allowed only before credential rows are provisioned.
        encoded_hash = os.environ.get("TOIR_ACCESS_KEY_HASH", "")
        if (
            not rows
            and self._legacy_account_uuid()
            and encoded_hash
            and self._legacy_account_is_active()
            and self._verify_encoded(encoded_hash, access_key)
        ):
            return VerifiedAccount(self._env_account(), is_legacy=True)
        return None

    @staticmethod
    def _encoded_salt_hex(encoded_hash: str) -> str:
        try:
            salt = encoded_hash.split("$")[4]
            salt += "=" * (-len(salt) % 4)
            return base64.b64decode(salt, validate=True).hex()
        except (IndexError, ValueError, TypeError) as exc:
            raise AuthConfigurationError("Argon2id PHC salt is invalid") from exc

    @staticmethod
    def _validate_access_key(access_key: str) -> str:
        if not isinstance(access_key, str) or ACCESS_KEY_PATTERN.fullmatch(access_key) is None:
            raise AuthConfigurationError("Access key has an invalid format")
        return access_key

    @staticmethod
    def _validate_key_salt(key_salt: str) -> str:
        if not isinstance(key_salt, str) or re.fullmatch(r"[0-9a-f]{32}", key_salt) is None:
            raise AuthConfigurationError("Credential key_salt is invalid")
        return key_salt

    @classmethod
    def generate_access_key(cls) -> str:
        """Generate a ten-character key without ambiguous glyphs."""
        return "".join(secrets.choice(ACCESS_KEY_ALPHABET) for _ in range(ACCESS_KEY_LENGTH))

    def _hash_access_key(self, access_key: str, key_salt: bytes) -> tuple[str, str]:
        self._validate_access_key(access_key)
        if len(key_salt) != KEY_SALT_BYTES:
            raise AuthConfigurationError("Credential key_salt must contain 16 bytes")
        key_hash = self._ph.hash(access_key, salt=key_salt)
        encoded_salt = self._encoded_salt_hex(key_hash)
        if encoded_salt != key_salt.hex():
            raise AuthConfigurationError("Argon2id PHC salt does not match key_salt")
        return key_hash, encoded_salt

    def provision_employee_access(self, employee_id: str, access_key: str) -> None:
        """Store one employee credential using an explicit random salt."""
        key_salt = secrets.token_bytes(KEY_SALT_BYTES)
        key_hash, key_salt_hex = self._hash_access_key(access_key, key_salt)
        with self.pool.cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO promscan.access_key_credentials (
                    employee_id, key_hash, key_salt
                ) VALUES (%s, %s, %s)
                """,
                (employee_id, key_hash, key_salt_hex),
            )

    def rotate_employee_access(self, employee_id: str) -> RotatedAccessKey:
        """Replace a credential in one transaction and return rollback material."""
        access_key = self.generate_access_key()
        key_hash, key_salt = self._hash_access_key(
            access_key, secrets.token_bytes(KEY_SALT_BYTES)
        )
        with self.pool.cursor(commit=True) as cur:
            cur.execute(
                """
                SELECT key_hash, key_salt
                FROM promscan.access_key_credentials
                WHERE employee_id = %s
                FOR UPDATE
                """,
                (employee_id,),
            )
            previous = cur.fetchone()
            if previous is None:
                raise DatabaseError("Employee credential was not found")
            previous_hash = previous.get("key_hash")
            previous_salt = previous.get("key_salt")
            if not previous_hash or not previous_salt:
                raise AuthConfigurationError("Credential key_salt is missing")
            self._validate_key_salt(previous_salt)
            if self._encoded_salt_hex(previous_hash) != previous_salt:
                raise AuthConfigurationError("Credential key_salt does not match its PHC hash")
            cur.execute(
                """
                UPDATE promscan.access_key_credentials
                SET key_hash = %s, key_salt = %s
                WHERE employee_id = %s
                """,
                (key_hash, key_salt, employee_id),
            )
        return RotatedAccessKey(access_key, previous_hash, previous_salt)

    def restore_employee_access(
        self, employee_id: str, key_hash: str, key_salt: str
    ) -> None:
        """Restore a previous credential after an invitation delivery failure."""
        self._validate_key_salt(key_salt)
        if self._encoded_salt_hex(key_hash) != key_salt:
            raise AuthConfigurationError("Credential key_salt does not match its PHC hash")
        with self.pool.cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE promscan.access_key_credentials
                SET key_hash = %s, key_salt = %s
                WHERE employee_id = %s
                RETURNING employee_id
                """,
                (key_hash, key_salt, employee_id),
            )
            if cur.fetchone() is None:
                raise DatabaseError("Employee credential was not found")

    @staticmethod
    def _env_account() -> AuthAccount:
        role_value = os.environ.get("TOIR_ROLE", "engineer").strip().lower()
        role: Role = role_value if role_value in ROLE_PERMISSIONS else "engineer"
        return AuthAccount(
            id=os.environ.get("TOIR_ACCOUNT_ID", "emp-001"),
            full_name=os.environ.get("TOIR_FULL_NAME", "Инженер ТОиР"),
            email=os.environ.get("TOIR_EMAIL", "engineer@localhost"),
            role=role,
            permissions=ROLE_PERMISSIONS[role],
        )

    # ------------------------------------------------------------------
    # Rate limiting входа (credentials-БД + memory-fallback)
    # ------------------------------------------------------------------

    def reserve_login_attempt(
        self, access_key: str, source_id: str
    ) -> Optional[LoginReservation]:
        now_dt = self._now()
        identifier_fp = self._fp("identifier", access_key.strip().upper())
        source_fp = self._fp("source", source_id)
        try:
            with self.pool.cursor(commit=True) as cur:
                lock_keys = sorted(
                    {
                        int.from_bytes(hashlib.sha256(fp).digest()[:8], "big", signed=True)
                        for fp in (identifier_fp, source_fp)
                    }
                )
                for lock_key in lock_keys:
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
                cutoff = now_dt - LOGIN_WINDOW
                cur.execute(
                    """
                    DELETE FROM promscan.auth_login_attempts
                    WHERE (identifier_fingerprint = %s OR source_fingerprint = %s)
                      AND attempted_at < %s
                    """,
                    (identifier_fp, source_fp, cutoff),
                )
                cur.execute(
                    """
                    SELECT count(*) AS failures
                    FROM promscan.auth_login_attempts
                    WHERE identifier_fingerprint = %s
                      AND was_successful = false
                      AND attempted_at > %s
                    """,
                    (identifier_fp, cutoff),
                )
                identifier_failures = int(cur.fetchone()["failures"])
                cur.execute(
                    """
                    SELECT count(*) AS failures
                    FROM promscan.auth_login_attempts
                    WHERE source_fingerprint = %s
                      AND was_successful = false
                      AND attempted_at > %s
                    """,
                    (source_fp, cutoff),
                )
                source_failures = int(cur.fetchone()["failures"])
                if (
                    identifier_failures >= LOGIN_FAILURE_LIMIT
                    or source_failures >= LOGIN_FAILURE_LIMIT
                ):
                    return None
                cur.execute(
                    """
                    INSERT INTO promscan.auth_login_attempts (
                        identifier_fingerprint, source_fingerprint, was_successful
                    ) VALUES (%s, %s, false)
                    RETURNING id
                    """,
                    (identifier_fp, source_fp),
                )
                attempt_id = int(cur.fetchone()["id"])
            return LoginReservation(identifier_fp, source_fp, attempt_id=attempt_id)
        except DatabaseError:
            return self._mem_reserve(identifier_fp, source_fp, now_dt)

    def _mem_reserve(
        self, identifier_fp: bytes, source_fp: bytes, now_dt: datetime
    ) -> Optional[LoginReservation]:
        attempt_keys = {identifier_fp.hex(), source_fp.hex()}
        nonce = secrets.token_hex(16)
        with self._lock:
            # Текущая пара должна пережить eviction: иначе при заполненном
            # fallback-состоянии можно было бы удалить активный lockout до
            # проверки и снова пропустить попытку.
            self._prune_memory_state(now_dt, protected_keys=attempt_keys)
            active_attempts: dict[str, list[tuple[datetime, str]]] = {}
            for key in attempt_keys:
                lock = self._mem_lockout.get(key)
                if lock and lock > now_dt:
                    return None
                active_attempts[key] = [
                    attempt
                    for attempt in self._mem_attempts.get(key, [])
                    if now_dt - attempt[0] < LOGIN_WINDOW
                ]
            if any(len(attempts) >= LOGIN_FAILURE_LIMIT for attempts in active_attempts.values()):
                for key in attempt_keys:
                    self._mem_lockout[key] = now_dt + LOGIN_LOCKOUT
                self._prune_memory_state(now_dt, protected_keys=attempt_keys)
                return None
            for key, attempts in active_attempts.items():
                attempts.append((now_dt, nonce))
                self._mem_attempts[key] = attempts
            self._prune_memory_state(now_dt, protected_keys=attempt_keys)
            return LoginReservation(
                identifier_fp, source_fp, memory_nonce=nonce
            )

    @staticmethod
    def _memory_last_seen(value: object) -> datetime:
        if isinstance(value, list):
            return max(
                (attempt[0] for attempt in value),
                default=datetime.min.replace(tzinfo=timezone.utc),
            )
        if isinstance(value, datetime):
            return value
        return datetime.min.replace(tzinfo=timezone.utc)

    def _prune_memory_state(
        self,
        now_dt: datetime,
        protected_keys: set[str] | frozenset[str] = frozenset(),
    ) -> None:
        """Глобально очищает и ограничивает memory fallback rate limiter-а."""
        for key, attempts in list(self._mem_attempts.items()):
            active = [
                attempt
                for attempt in attempts
                if now_dt - attempt[0] < LOGIN_WINDOW
            ]
            if active:
                self._mem_attempts[key] = active
            else:
                self._mem_attempts.pop(key, None)

        for key, lockout in list(self._mem_lockout.items()):
            if lockout <= now_dt:
                self._mem_lockout.pop(key, None)

        max_keys = max(LOGIN_MEMORY_MAX_KEYS, len(protected_keys))
        for mapping in (self._mem_attempts, self._mem_lockout):
            overflow = len(mapping) - max_keys
            if overflow <= 0:
                continue
            candidates = [key for key in mapping if key not in protected_keys]
            candidates.sort(key=lambda key: self._memory_last_seen(mapping[key]))
            for key in candidates[:overflow]:
                mapping.pop(key, None)

    def mark_login_success(self, reservation: LoginReservation) -> None:
        if reservation.attempt_id is not None:
            with self.pool.cursor(commit=True) as cur:
                cur.execute(
                    """
                    UPDATE promscan.auth_login_attempts
                    SET was_successful = true
                    WHERE id = %s
                      AND identifier_fingerprint = %s
                      AND source_fingerprint = %s
                      AND was_successful = false
                    """,
                    (
                        reservation.attempt_id,
                        reservation.identifier_fingerprint,
                        reservation.source_fingerprint,
                    ),
                )
            return

        if reservation.memory_nonce is None:
            return
        with self._lock:
            for key in (
                reservation.identifier_fingerprint.hex(),
                reservation.source_fingerprint.hex(),
            ):
                attempts = self._mem_attempts.get(key, [])
                remaining = [
                    attempt for attempt in attempts if attempt[1] != reservation.memory_nonce
                ]
                if remaining:
                    self._mem_attempts[key] = remaining
                else:
                    self._mem_attempts.pop(key, None)
                self._mem_lockout.pop(key, None)

    @staticmethod
    def _fp(kind: str, value: str) -> bytes:
        # Схема хранит HMAC-отпечаток нормализованного идентификатора.
        # Секрет схемы — переменная LOGIN_FP_SECRET (вне БД, см. database/README.md).
        secret_value = os.environ.get("LOGIN_FP_SECRET", "").strip()
        if not secret_value:
            raise AuthConfigurationError("LOGIN_FP_SECRET must be configured")
        secret = secret_value.encode("utf-8")
        payload = f"{kind}:{value.strip().lower()}".encode("utf-8")
        return hmac.new(secret, payload, hashlib.sha256).digest()

    # ------------------------------------------------------------------
    # Сессии (PostgreSQL)
    # ------------------------------------------------------------------

    def login_reserved(
        self,
        access_key: str,
        source_id: str,
        reservation: LoginReservation,
    ) -> AuthLoginResponse | None:
        identifier_fp = self._fp("identifier", access_key.strip().upper())
        source_fp = self._fp("source", source_id)
        if not (
            hmac.compare_digest(identifier_fp, reservation.identifier_fingerprint)
            and hmac.compare_digest(source_fp, reservation.source_fingerprint)
        ):
            raise AuthConfigurationError("Login reservation does not match request")
        verified = self._verify_key_with_source(access_key)
        if verified is None:
            return None
        account = verified.account

        now = self._now()
        expires_at = now + SESSION_TTL
        token = secrets.token_urlsafe(32)
        with self.pool.cursor(commit=True) as cur:
            legacy_employee_id = self._legacy_account_uuid()
            employee_id = (
                legacy_employee_id
                if verified.is_legacy and legacy_employee_id
                else self._account_uuid(account.id)
            )
            if verified.is_legacy:
                encoded_hash = os.environ.get("TOIR_ACCESS_KEY_HASH", "")
                if encoded_hash:
                    cur.execute(
                        """
                        SELECT key_hash, key_salt FROM promscan.access_key_credentials
                        WHERE employee_id = %s
                        """,
                        (employee_id,),
                    )
                    legacy_credential = cur.fetchone()
                    if legacy_credential is None:
                        cur.execute(
                            """
                            INSERT INTO promscan.access_key_credentials (
                                employee_id, key_hash, key_salt
                            ) VALUES (%s, %s, %s)
                            ON CONFLICT (employee_id) DO NOTHING
                            """,
                            (employee_id, encoded_hash, self._encoded_salt_hex(encoded_hash)),
                        )
                        cur.execute(
                            """
                            SELECT key_hash, key_salt FROM promscan.access_key_credentials
                            WHERE employee_id = %s
                            """,
                            (employee_id,),
                        )
                        legacy_credential = cur.fetchone()
                    if legacy_credential is None:
                        raise AuthConfigurationError("Could not provision the legacy credential")
                    if not self._verify_encoded(legacy_credential["key_hash"], access_key):
                        raise AuthConfigurationError(
                            "Legacy account UUID conflicts with a provisioned credential"
                        )
                    if (
                        not legacy_credential["key_salt"]
                        or self._encoded_salt_hex(legacy_credential["key_hash"])
                        != legacy_credential["key_salt"]
                    ):
                        raise AuthConfigurationError(
                            "Legacy credential has an invalid key_salt"
                        )
            cur.execute(
                """
                INSERT INTO promscan.auth_sessions (employee_id, session_token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (employee_id, self._token_hash(token), expires_at),
            )
            if reservation.attempt_id is not None:
                cur.execute(
                    """
                    UPDATE promscan.auth_login_attempts
                    SET was_successful = true
                    WHERE id = %s
                      AND identifier_fingerprint = %s
                      AND source_fingerprint = %s
                      AND was_successful = false
                    """,
                    (
                        reservation.attempt_id,
                        reservation.identifier_fingerprint,
                        reservation.source_fingerprint,
                    ),
                )
        if reservation.memory_nonce is not None:
            self.mark_login_success(reservation)
        return AuthLoginResponse(
            session_token=token,
            expires_at=self._iso(expires_at),
            account=account,
        )

    @staticmethod
    def _account_uuid(account_id: str) -> str:
        try:
            import uuid as _uuid

            return str(_uuid.UUID(str(account_id)))
        except (ValueError, TypeError, AttributeError):
            # Легаси-аккаунты окружения (emp-001) не являются UUID:
            # сессии таких аккаунтов храним под детерминированным UUIDv5.
            import uuid as _uuid

            return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"promscan:{account_id}"))

    @classmethod
    def _legacy_account_uuid(cls) -> Optional[str]:
        if not os.environ.get("TOIR_ACCESS_KEY_HASH", ""):
            return None
        account_id = os.environ.get("TOIR_ACCOUNT_ID", "emp-001")
        try:
            import uuid as _uuid

            parsed = _uuid.UUID(str(account_id))
        except (ValueError, TypeError, AttributeError):
            return cls._account_uuid(account_id)
        return str(parsed)

    def _legacy_account_is_active(self) -> bool:
        """Return the employee-directory state for the configured legacy account.

        Older deployments may use a virtual legacy account without an employee
        row. Preserve that fallback until the account is represented in the
        employee directory; once a row exists, its ``is_active`` flag is the
        source of truth just like for provisioned accounts.
        """
        employee_id = self._legacy_account_uuid()
        if employee_id is None:
            return False
        with self.employees_pool.cursor() as cur:
            cur.execute(
                """
                SELECT is_active
                FROM promscan.employees
                WHERE id = %s
                """,
                (employee_id,),
            )
            employee = cur.fetchone()
        return employee is None or bool(employee["is_active"])

    def get_account(self, token: str) -> AuthAccount | None:
        now = self._now()
        with self.pool.cursor() as cur:
            cur.execute(
                """
                SELECT employee_id FROM promscan.auth_sessions
                WHERE session_token_hash = %s
                  AND revoked_at IS NULL AND expires_at > %s
                """,
                (self._token_hash(token), now),
            )
            row = cur.fetchone()
        if row is None:
            return None
        employee_id = str(row["employee_id"])
        if employee_id == self._legacy_account_uuid():
            if not self._legacy_account_is_active():
                return None
            return self._env_account()
        with self.employees_pool.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, email, role
                FROM promscan.employees
                WHERE id = %s AND is_active
                """,
                (employee_id,),
            )
            employee = cur.fetchone()
        if employee is None:
            return None
        return AuthAccount(
            id=str(employee["id"]),
            full_name=employee["full_name"],
            email=employee["email"],
            role=employee["role"],
            permissions=ROLE_PERMISSIONS.get(employee["role"], ["scan"]),
        )

    def revoke(self, token: str) -> None:
        with self.pool.cursor(commit=True) as cur:
            cur.execute(
                """
                UPDATE promscan.auth_sessions
                SET revoked_at = now()
                WHERE session_token_hash = %s AND revoked_at IS NULL
                """,
                (self._token_hash(token),),
            )

    def revoke_employee_access(self, employee_id: str) -> None:
        """Remove a credential and its dependent authentication sessions."""
        with self.pool.cursor(commit=True) as cur:
            cur.execute(
                """
                DELETE FROM promscan.access_key_credentials
                WHERE employee_id = %s
                """,
                (employee_id,),
            )
