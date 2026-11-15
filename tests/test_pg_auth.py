"""PostgreSQL integration tests for authentication across isolated databases.

The test DSNs are admin connections used only to create random disposable
databases. Production DSNs are rejected before any schema or data is changed.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import auth as auth_router
from app.services.auth import AuthService
from app.services.db import PostgresPool
from app.services.employees import EmployeeService


ROOT = Path(__file__).resolve().parents[1]
EMPLOYEES_SCHEMA = ROOT / "database/sql/employees/001_schema.sql"
EMPLOYEES_MIGRATION_002 = ROOT / "database/sql/employees/002_invitation_states.sql"
CREDENTIALS_SCHEMA = ROOT / "database/sql/credentials/001_schema.sql"
CREDENTIALS_MIGRATION_002 = ROOT / "database/sql/credentials/002_key_salt_and_login_audit.sql"
CREDENTIALS_MIGRATION_003 = ROOT / "database/sql/credentials/003_enforce_key_salt.sql"


def _test_dsn(name: str) -> str:
    dsn = os.getenv(name, "").strip()
    if not dsn:
        pytest.skip(f"{name} is not set; PostgreSQL auth integration tests skipped")
    production_dsns = {
        os.getenv(key, "").strip()
        for key in (
            "DATABASE_URL",
            "DATABASE_CATALOG_URL",
            "DATABASE_TASKS_URL",
            "DATABASE_EMPLOYEES_URL",
            "DATABASE_CREDENTIALS_URL",
        )
    }
    if dsn in production_dsns:
        pytest.fail(f"{name} matches a production DSN; refusing to run")
    return dsn


@pytest.fixture(scope="session")
def auth_test_pools():
    credentials_source = _test_dsn("DATABASE_TEST_CREDENTIALS_URL")
    employees_source = _test_dsn("DATABASE_TEST_EMPLOYEES_URL")
    psycopg = pytest.importorskip("psycopg")
    databases: list[tuple[str, str]] = []
    suffix = uuid.uuid4().hex[:10]

    def create_database(source_dsn: str, name: str) -> tuple[str, str]:
        params = psycopg.conninfo.conninfo_to_dict(source_dsn)
        admin_params = dict(params, dbname="postgres")
        admin_dsn = psycopg.conninfo.make_conninfo(**admin_params)
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name))
            )
        return psycopg.conninfo.make_conninfo(**dict(params, dbname=name)), admin_dsn

    credentials_db = f"promscan_auth_credentials_pytest_{suffix}"
    employees_db = f"promscan_auth_employees_pytest_{suffix}"
    credentials_dsn, credentials_admin = create_database(credentials_source, credentials_db)
    databases.append((credentials_admin, credentials_db))
    try:
        employees_dsn, employees_admin = create_database(employees_source, employees_db)
        databases.append((employees_admin, employees_db))
        with psycopg.connect(credentials_dsn, autocommit=True) as conn:
            for schema_path in (
                CREDENTIALS_SCHEMA,
                CREDENTIALS_MIGRATION_002,
                CREDENTIALS_MIGRATION_003,
            ):
                conn.execute(schema_path.read_text(encoding="utf-8"))
        with psycopg.connect(employees_dsn, autocommit=True) as conn:
            conn.execute(EMPLOYEES_SCHEMA.read_text(encoding="utf-8"))
            conn.execute(EMPLOYEES_MIGRATION_002.read_text(encoding="utf-8"))
        yield PostgresPool(credentials_dsn, "test credentials"), PostgresPool(
            employees_dsn, "test employees"
        )
    finally:
        for admin_dsn, dbname in reversed(databases):
            with psycopg.connect(admin_dsn, autocommit=True) as conn:
                try:
                    conn.execute(
                        psycopg.sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                            psycopg.sql.Identifier(dbname)
                        )
                    )
                except psycopg.errors.SyntaxError:
                    conn.execute(
                        psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                            psycopg.sql.Identifier(dbname)
                        )
                    )


@pytest.fixture
def auth_client(auth_test_pools, monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    credentials_pool, employees_pool = auth_test_pools
    with psycopg.connect(credentials_pool.dsn) as conn:
        conn.execute(
            "TRUNCATE promscan.auth_sessions, "
            "promscan.email_verification_codes, "
            "promscan.auth_login_attempts, promscan.access_key_credentials"
        )
    with psycopg.connect(employees_pool.dsn) as conn:
        conn.execute("TRUNCATE promscan.employees")
    employee_id = uuid.uuid4()
    access_key = "B23456789C"
    key_hash = PasswordHasher().hash(access_key)
    key_salt = AuthService._encoded_salt_hex(key_hash)
    monkeypatch.setenv("LOGIN_FP_SECRET", "integration-test-secret")

    with psycopg.connect(employees_pool.dsn) as conn:
        conn.execute(
            """
            INSERT INTO promscan.employees (id, full_name, email, role)
            VALUES (%s, %s, %s, 'engineer')
            """,
            (employee_id, "Test Engineer", f"{employee_id}@example.test"),
        )
    with psycopg.connect(credentials_pool.dsn) as conn:
        conn.execute(
            """
            INSERT INTO promscan.access_key_credentials (employee_id, key_hash, key_salt)
            VALUES (%s, %s, %s)
            """,
            (employee_id, key_hash, key_salt),
        )

    service = AuthService(credentials_pool, employees_pool)
    monkeypatch.setattr(auth_router, "auth_service", service)
    app = FastAPI()
    app.include_router(auth_router.router)
    with TestClient(app) as client:
        yield client, access_key, employee_id, credentials_pool

    credentials_pool.close()
    employees_pool.close()


def test_login_me_logout_and_revocation(auth_client):
    client, access_key, employee_id, credentials_pool = auth_client
    response = client.post("/api/auth/login", json={"access_key": "b2 3456-789c"})
    assert response.status_code == 200
    body = response.json()
    assert body["account"]["id"] == str(employee_id)
    assert body["account"]["permissions"] == ["scan"]
    assert "key_hash" not in response.text
    token = body["session_token"]

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).json()["id"] == str(employee_id)
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    with credentials_pool.cursor() as cur:
        cur.execute(
            "SELECT octet_length(session_token_hash) AS size FROM promscan.auth_sessions"
        )
        assert cur.fetchone()["size"] == 32


def test_login_rejects_wrong_key_and_throttles_source(auth_client):
    client, access_key, _, _ = auth_client
    for _ in range(5):
        response = client.post("/api/auth/login", json={"access_key": "C23456789D"})
        assert response.status_code == 401
    assert client.post("/api/auth/login", json={"access_key": "C23456789D"}).status_code == 429
    assert client.post("/api/auth/login", json={"access_key": access_key}).status_code == 429


def test_correct_key_is_checked_on_fifth_attempt(auth_client):
    client, access_key, _, _ = auth_client
    for _ in range(4):
        assert client.post("/api/auth/login", json={"access_key": "C23456789D"}).status_code == 401
    assert client.post("/api/auth/login", json={"access_key": access_key}).status_code == 200


def test_employee_listing_and_deactivation_cascade(auth_test_pools):
    """Deactivation preserves the employee and removes credential dependents."""
    psycopg = pytest.importorskip("psycopg")
    credentials_pool, employees_pool = auth_test_pools
    active_id = uuid.uuid4()
    inactive_id = uuid.uuid4()
    key_hash = PasswordHasher().hash("integration-key")
    key_salt = AuthService._encoded_salt_hex(key_hash)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    with psycopg.connect(credentials_pool.dsn, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE promscan.auth_sessions, "
            "promscan.email_verification_codes, "
            "promscan.auth_login_attempts, promscan.access_key_credentials"
        )
    with psycopg.connect(employees_pool.dsn, autocommit=True) as conn:
        conn.execute("TRUNCATE promscan.employees")
        conn.execute(
            """
            INSERT INTO promscan.employees (id, full_name, email, role, is_active)
            VALUES (%s, %s, %s, 'engineer', true),
                   (%s, %s, %s, 'admin', false)
            """,
            (
                active_id,
                "Active Engineer",
                f"{active_id}@example.test",
                inactive_id,
                "Inactive Admin",
                f"{inactive_id}@example.test",
            ),
        )
    with psycopg.connect(credentials_pool.dsn, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO promscan.access_key_credentials (employee_id, key_hash, key_salt)
            VALUES (%s, %s, %s)
            """,
            (active_id, key_hash, key_salt),
        )
        conn.execute(
            """
            INSERT INTO promscan.auth_sessions
                (employee_id, session_token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (active_id, b"s" * 32, expires_at),
        )
        conn.execute(
            """
            INSERT INTO promscan.email_verification_codes
                (employee_id, code_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (active_id, b"c" * 32, expires_at),
        )

    service = EmployeeService(
        employees_pool=employees_pool,
        auth_service=AuthService(credentials_pool, employees_pool),
    )

    assert [profile.id for profile in service.list_active()] == [active_id]

    service.deactivate(active_id)

    with psycopg.connect(employees_pool.dsn) as conn:
        employee = conn.execute(
            "SELECT is_active FROM promscan.employees WHERE id = %s",
            (active_id,),
        ).fetchone()
        assert employee == (False,)
    with psycopg.connect(credentials_pool.dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM promscan.access_key_credentials WHERE employee_id = %s",
            (active_id,),
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM promscan.auth_sessions WHERE employee_id = %s",
            (active_id,),
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT count(*) FROM promscan.email_verification_codes WHERE employee_id = %s",
            (active_id,),
        ).fetchone() == (0,)

    # The employee row remains available for an idempotent repeat request.
    service.deactivate(active_id)
    with psycopg.connect(employees_pool.dsn) as conn:
        assert conn.execute(
            "SELECT id, is_active FROM promscan.employees WHERE id = %s",
            (active_id,),
        ).fetchone() == (active_id, False)
    assert service.list_active() == []


def test_access_key_rotation_updates_salt_and_revokes_active_sessions(auth_test_pools):
    credentials_pool, employees_pool = auth_test_pools
    employee_id = uuid.uuid4()
    old_key = "B23456789C"
    old_salt = b"o" * 16
    old_hash = PasswordHasher().hash(old_key, salt=old_salt)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    with credentials_pool.cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO promscan.access_key_credentials (employee_id, key_hash, key_salt)
            VALUES (%s, %s, %s)
            """,
            (employee_id, old_hash, old_salt.hex()),
        )
        cur.execute(
            """
            INSERT INTO promscan.auth_sessions
                (employee_id, session_token_hash, expires_at)
            VALUES (%s, %s, %s)
            """,
            (employee_id, b"r" * 32, expires_at),
        )

    rotated = AuthService(credentials_pool, employees_pool).rotate_employee_access(
        str(employee_id)
    )

    assert len(rotated.access_key) == 10
    assert PasswordHasher().verify(
        rotated.previous_key_hash, old_key
    )
    assert rotated.previous_key_salt == old_salt.hex()
    with credentials_pool.cursor() as cur:
        cur.execute(
            """
            SELECT c.key_hash, c.key_salt, s.revoked_at
            FROM promscan.access_key_credentials AS c
            JOIN promscan.auth_sessions AS s USING (employee_id)
            WHERE c.employee_id = %s
            """,
            (employee_id,),
        )
        row = cur.fetchone()
    assert row["key_hash"].startswith("$argon2id$")
    assert row["key_salt"] == AuthService._encoded_salt_hex(row["key_hash"])
    assert row["key_salt"] != old_salt.hex()
    assert PasswordHasher().verify(row["key_hash"], rotated.access_key)
    assert row["revoked_at"] is not None
    assert rotated.access_key not in repr(row)
