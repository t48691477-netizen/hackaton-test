"""PostgreSQL-провайдер соединений для FastAPI-приложения.

Приложение работает с четырьмя базами, описанными в database/README.md:
  DATABASE_URL            — каталог оборудования (schema promscan)
  DATABASE_TASKS_URL      — задачи/акты (schema promscan)
  DATABASE_EMPLOYEES_URL  — справочник сотрудников (schema promscan)
  DATABASE_CREDENTIALS_URL— ключи и сессии (schema promscan)

Пул создаётся лениво при первом обращении, поэтому импорт модуля не требует
доступного сервера (это нужно тестам и импорту app.services.*). Все DSN
читаются один раз при создании провайдера; для тестов DSN можно передать
конструктору или подменить переменными окружения до импорта.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

try:  # pragma: no cover - выбор драйвера зависит от окружения
    import psycopg  # type: ignore
    import psycopg_pool  # type: ignore
    from psycopg.rows import dict_row  # type: ignore

    _HAS_PSYCOPG = True
except Exception:  # pragma: no cover
    psycopg = None
    psycopg_pool = None
    dict_row = None
    _HAS_PSYCOPG = False


class DatabaseError(RuntimeError):
    """Ожидаемая ошибка БД, безопасная для передачи в HTTP-слой."""


class DatabaseNotConfigured(DatabaseError):
    pass


class DatabaseUnavailable(DatabaseError):
    pass


class PostgresPool:
    """Ленивый thread-safe пул к одной PostgreSQL-базе."""

    def __init__(self, dsn: str, name: str, min_size: int = 1, max_size: int = 5):
        if not dsn or not dsn.strip():
            raise DatabaseNotConfigured(f"{name}: DSN не задан")
        self.dsn = dsn.strip()
        self.name = name
        self._min_size = max(1, int(min_size))
        self._max_size = max(self._min_size, int(max_size))
        self._pool = None
        self._lock = threading.Lock()

    def _ensure_pool(self):
        if self._pool is not None:
            return self._pool
        with self._lock:
            if self._pool is not None:
                return self._pool
            if not _HAS_PSYCOPG:
                raise DatabaseUnavailable(
                    "PostgreSQL-драйвер не установлен: pip install 'psycopg[binary,pool]'"
                )
            try:
                self._pool = psycopg_pool.ConnectionPool(
                    conninfo=self.dsn,
                    min_size=self._min_size,
                    max_size=self._max_size,
                    kwargs={"row_factory": dict_row},
                    open=True,
                    timeout=30,
                )
            except Exception as exc:
                raise DatabaseUnavailable(
                    f"{self.name}: не удалось подключиться к PostgreSQL"
                ) from exc
        return self._pool

    @contextmanager
    def connection(self) -> Iterator["psycopg.Connection"]:
        try:
            pool = self._ensure_pool()
        except DatabaseError:
            raise
        try:
            conn = pool.getconn(timeout=30)
        except Exception as exc:
            raise DatabaseUnavailable(
                f"{self.name}: не удалось получить соединение PostgreSQL"
            ) from exc
        try:
            yield conn
        finally:
            try:
                pool.putconn(conn)
            except Exception as exc:
                raise DatabaseUnavailable(
                    f"{self.name}: не удалось вернуть соединение PostgreSQL в пул"
                ) from exc

    @contextmanager
    def cursor(self, *, commit: bool = False):
        with self.connection() as conn:
            try:
                with conn.cursor() as cur:
                    yield cur
                if commit:
                    conn.commit()
            except DatabaseError:
                conn.rollback()
                raise
            except Exception as exc:
                conn.rollback()
                if _HAS_PSYCOPG and isinstance(exc, psycopg.Error):
                    raise DatabaseError(
                        f"{self.name}: PostgreSQL-операция не удалась"
                    ) from exc
                raise

    def ping(self) -> None:
        with self.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()

    def close(self) -> None:
        with self._lock:
            if self._pool is not None:
                try:
                    self._pool.close()
                except Exception:
                    pass
                self._pool = None


class Pools:
    """Набор пулов по DSN из окружения с ленивой инициализацией."""

    def __init__(self):
        self._pools: dict[str, PostgresPool] = {}
        self._lock = threading.Lock()

    def _dsn(self, key: str, env: str, fallback_env: Optional[str] = None) -> str:
        dsn = os.getenv(env, "").strip()
        if not dsn and fallback_env:
            dsn = os.getenv(fallback_env, "").strip()
        return dsn

    def get(self, key: str) -> PostgresPool:
        with self._lock:
            pool = self._pools.get(key)
            if pool is not None:
                return pool
        # Создание пула вне глобальной блокировки: пинг сервера может занять
        # время, а другие потоки не должны ждать на глобальном lock.
        if key == "catalog":
            env, fallback = "DATABASE_URL", "DATABASE_CATALOG_URL"
        elif key == "tasks":
            env, fallback = "DATABASE_TASKS_URL", "DATABASE_URL"
        elif key == "employees":
            env, fallback = "DATABASE_EMPLOYEES_URL", "DATABASE_URL"
        elif key == "credentials":
            env, fallback = "DATABASE_CREDENTIALS_URL", "DATABASE_URL"
        else:
            raise KeyError(f"Неизвестный пул: {key}")
        dsn = self._dsn(key, env, fallback)
        pool = PostgresPool(dsn, name=key)
        with self._lock:
            existing = self._pools.get(key)
            if existing is not None:
                pool.close()
                return existing
            self._pools[key] = pool
            return pool

    def close_all(self) -> None:
        with self._lock:
            pools = list(self._pools.values())
            self._pools.clear()
        for pool in pools:
            pool.close()


pools = Pools()
