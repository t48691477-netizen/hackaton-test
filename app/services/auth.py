import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.schemas.auth import AuthAccount, AuthLoginResponse, Permission, Role


SESSION_TTL = timedelta(hours=8)
LOGIN_WINDOW = timedelta(minutes=10)
LOGIN_LOCKOUT = timedelta(minutes=10)
LOGIN_FAILURE_LIMIT = 5
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    "director": ["scan", "dispatch", "users"],
    "admin": ["scan", "dispatch", "users"],
    "dispatcher": ["scan", "dispatch"],
    "engineer": ["scan"],
}


class AuthConfigurationError(Exception):
    pass


class AuthService:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    account_json TEXT
                )"""
            )
            try:
                conn.execute("ALTER TABLE auth_sessions ADD COLUMN account_json TEXT")
            except sqlite3.OperationalError:
                pass
            conn.execute(
                """CREATE TABLE IF NOT EXISTS auth_login_attempts (
                    client_id TEXT PRIMARY KEY,
                    failures INTEGER NOT NULL,
                    window_started_at TEXT NOT NULL,
                    blocked_until TEXT
                )"""
            )
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def _verify_key(cls, access_key: str) -> AuthAccount | None:
        normalized = access_key.replace(" ", "").replace("-", "").upper()
        encoded_hash = os.environ.get("TOIR_ACCESS_KEY_HASH", "").strip()
        if encoded_hash:
            if not encoded_hash.startswith("$argon2id$"):
                raise AuthConfigurationError("TOIR_ACCESS_KEY_HASH must contain an Argon2id hash")
            try:
                if PasswordHasher().verify(encoded_hash, access_key) or PasswordHasher().verify(encoded_hash, normalized):
                    if PasswordHasher().check_needs_rehash(encoded_hash):
                        raise AuthConfigurationError("TOIR_ACCESS_KEY_HASH must use current Argon2id parameters")
                    return cls._account()
            except VerifyMismatchError:
                pass
            except AuthConfigurationError:
                raise
            except Exception as exc:
                raise AuthConfigurationError("TOIR_ACCESS_KEY_HASH is invalid") from exc

        # Default system accounts out-of-the-box
        default_accounts: dict[str, AuthAccount] = {
            "8ZG9X5N7KX": AuthAccount(
                id="emp-001",
                full_name="Инженер ТОиР (мобильный)",
                email="engineer@kst-energo.ru",
                role="engineer",
                permissions=["scan"],
            ),
            "PSCDRT2345": AuthAccount(
                id="director",
                full_name="Генеральный директор",
                email="director@kst-energo.ru",
                role="director",
                permissions=["scan", "dispatch", "users"],
            ),
            "PSCADM3456": AuthAccount(
                id="admin",
                full_name="Администратор системы",
                email="admin@kst-energo.ru",
                role="admin",
                permissions=["scan", "dispatch", "users"],
            ),
            "PSCDSP4567": AuthAccount(
                id="dispatcher",
                full_name="Диспетчер смены",
                email="dispatcher@kst-energo.ru",
                role="dispatcher",
                permissions=["scan", "dispatch"],
            ),
            "PSCENG5678": AuthAccount(
                id="engineer-002",
                full_name="Анна Петрова (Инженер)",
                email="a.petrova@kst-energo.ru",
                role="engineer",
                permissions=["scan"],
            ),
        }
        if normalized in default_accounts:
            return default_accounts[normalized]

        return None

    @staticmethod
    def _account() -> AuthAccount:
        role_value = os.environ.get("TOIR_ROLE", "engineer").strip().lower()
        role: Role = role_value if role_value in ROLE_PERMISSIONS else "engineer"
        return AuthAccount(
            id=os.environ.get("TOIR_ACCOUNT_ID", "emp-001"),
            full_name=os.environ.get("TOIR_FULL_NAME", "Инженер ТОиР"),
            email=os.environ.get("TOIR_EMAIL", "engineer@localhost"),
            role=role,
            permissions=ROLE_PERMISSIONS[role],
        )

    def reserve_login_attempt(self, client_id: str) -> bool:
        now_dt = self._now()
        now = self._iso(now_dt)
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM auth_login_attempts WHERE window_started_at <= ? AND (blocked_until IS NULL OR blocked_until <= ?)",
                (self._iso(now_dt - LOGIN_WINDOW), now),
            )
            row = conn.execute(
                "SELECT failures, window_started_at, blocked_until FROM auth_login_attempts WHERE client_id = ?",
                (client_id,),
            ).fetchone()
            if row and row[2] and row[2] > now:
                return False
            if row is None or now_dt - datetime.fromisoformat(row[1].replace("Z", "+00:00")) > LOGIN_WINDOW:
                failures = 1
                window_started_at = now
            else:
                failures = row[0] + 1
                window_started_at = row[1]
            blocked_until = self._iso(now_dt + LOGIN_LOCKOUT) if failures >= LOGIN_FAILURE_LIMIT else None
            conn.execute(
                """INSERT INTO auth_login_attempts (client_id, failures, window_started_at, blocked_until)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(client_id) DO UPDATE SET failures = excluded.failures,
                     window_started_at = excluded.window_started_at,
                     blocked_until = excluded.blocked_until""",
                (client_id, failures, window_started_at, blocked_until),
            )
            return True

    def clear_login_failures(self, client_id: str) -> None:
        with self._connection() as conn:
            conn.execute("DELETE FROM auth_login_attempts WHERE client_id = ?", (client_id,))

    def login_reserved(self, access_key: str, client_id: str) -> AuthLoginResponse | None:
        account = self._verify_key(access_key)
        if account is None:
            return None
        self.clear_login_failures(client_id)

        now = self._now()
        expires_at = now + SESSION_TTL
        token = secrets.token_urlsafe(32)
        account_json = account.model_dump_json() if hasattr(account, "model_dump_json") else json.dumps(account.dict())
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO auth_sessions (token_hash, created_at, expires_at, account_json) VALUES (?, ?, ?, ?)",
                (self._token_hash(token), self._iso(now), self._iso(expires_at), account_json),
            )
        return AuthLoginResponse(
            session_token=token,
            expires_at=self._iso(expires_at),
            account=account,
        )

    def get_account(self, token: str) -> AuthAccount | None:
        now = self._iso(self._now())
        with self._connection() as conn:
            row = conn.execute(
                """SELECT account_json FROM auth_sessions
                   WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?""",
                (self._token_hash(token), now),
            ).fetchone()
        if not row:
            return None
        if row[0]:
            try:
                data = json.loads(row[0])
                return AuthAccount(**data)
            except Exception:
                pass
        return self._account()

    def revoke(self, token: str) -> None:
        now = self._iso(self._now())
        with self._connection() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (now, self._token_hash(token)),
            )
