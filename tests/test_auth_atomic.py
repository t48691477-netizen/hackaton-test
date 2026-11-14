import json
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.auth import AuthService, LOGIN_FAILURE_LIMIT


def test_concurrent_attempt_reservation_is_atomic(tmp_path, monkeypatch):
    db = tmp_path / "auth.sqlite"
    service = AuthService(db)
    monkeypatch.setenv("TOIR_ACCESS_KEY_HASH", "$argon2id$invalid")
    barrier = threading.Barrier(LOGIN_FAILURE_LIMIT + 3)

    def attempt(_):
        barrier.wait()
        return service.reserve_login_attempt("203.0.113.9")

    with ThreadPoolExecutor(max_workers=LOGIN_FAILURE_LIMIT + 3) as pool:
        results = list(pool.map(attempt, range(LOGIN_FAILURE_LIMIT + 3)))

    assert results.count(True) == LOGIN_FAILURE_LIMIT
    assert results.count(False) == 3
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT failures, blocked_until FROM auth_login_attempts").fetchone()
    assert row[0] == LOGIN_FAILURE_LIMIT
    assert row[1]


def test_expired_attempt_rows_are_pruned_on_new_reservation(tmp_path):
    db = tmp_path / "auth.sqlite"
    service = AuthService(db)
    service.reserve_login_attempt("192.0.2.10")
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE auth_login_attempts SET window_started_at='2000-01-01T00:00:00Z', blocked_until=NULL")

    assert service.reserve_login_attempt("192.0.2.11")
    with sqlite3.connect(db) as conn:
        clients = conn.execute("SELECT client_id FROM auth_login_attempts").fetchall()
    assert clients == [("192.0.2.11",)]
