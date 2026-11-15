"""PostgreSQL-тесты хранилища отчётов/задач (promscan.reports).

Проверяют SQL-контракт хранилища задач из ``database/sql/tasks``:

* новые задачи создаются только в статусе ``open`` и без отметок
  жизненного цикла (``started_at``/``completed_at``);
* переход ``open → in_progress`` требует назначенного исполнителя,
  триггер сам проставляет ``started_at``;
* переход ``in_progress → closed`` проставляет ``completed_at``;
* отклонение ``open/in_progress → rejected`` с обязательным
  ``repair_comment`` и назначенным исполнителем работает после
  миграции ``002_rejected_status.sql`` (без неё тест скипается);
* невалидные переходы и ручная правка отметок/снимка исполнителя
  отклоняются ограничениями схемы;
* список задач выдаётся в порядке ``created_at DESC`` (как
  ``StorageService.get_reports``).

Как запускать
-------------

Интеграционные тесты требуют переменную окружения
``DATABASE_TEST_TASKS_URL`` — DSN, из которой тесты создают и удаляют
изолированную базу (роль должна иметь право CREATEDB):

    $env:DATABASE_TEST_TASKS_URL = "postgresql://<role>:<password>@127.0.0.1:5432/promscan_tasks"
    python -m pytest tests/test_pg_reports.py -v

Из DSN создаётся база вида ``promscan_tasks_pytest_<suffix>``, к ней
применяются ``database/sql/tasks/001_schema.sql`` и, если она существует,
``002_rejected_status.sql``; база удаляется по завершении сессии.
Если ``DATABASE_TEST_TASKS_URL`` не задана или psycopg (>= 3.2) не
установлен, интеграционные тесты пропускаются через ``pytest.skip``.

Маппинг легаси-статусов ``/api/reports`` (pending/in_progress/completed/
rejected) на SQL-состояния ``promscan.reports`` проверяется отдельными
юнит-тестами (``app.services.storage``): pending → open,
completed → closed. База для них не нужна.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TASKS_SQL_DIR = PROJECT_ROOT / "database" / "sql" / "tasks"
SCHEMA_001 = TASKS_SQL_DIR / "001_schema.sql"
SCHEMA_002 = TASKS_SQL_DIR / "002_rejected_status.sql"

TEST_DSN_ENV = "DATABASE_TEST_TASKS_URL"
TEST_DB_PREFIX = "promscan_tasks_pytest_"

# Базовые SQL-состояния promscan.reports из 001_schema.sql.
BASE_SQL_STATUSES = {"open", "in_progress", "closed"}

REPORT_COLUMNS = (
    "id, equipment_id, inspection_id, status, comment, photo_url, result, "
    "assignee_id, assignee_full_name, started_at, completed_at, repair_comment, "
    "created_at, updated_at"
)

# Фиктивная DSN: пулы app.services.storage создаются при импорте модуля,
# но подключаются к PostgreSQL лениво, поэтому соединения не происходит.
_DUMMY_DSN = "postgresql://pytest:pytest@127.0.0.1:1/pytest_no_connect"


# ---------------------------------------------------------------------------
# Хелперы для создания тестовой БД из DSN
# ---------------------------------------------------------------------------


def _import_psycopg():
    """Импортирует psycopg3 (не на уровне модуля — тесты без БД не требуют)."""
    try:
        import psycopg
    except ImportError as error:
        raise ImportError(
            "psycopg не установлен: pip install 'psycopg[binary]'"
        ) from error
    return psycopg


def _psycopg_version(module: Any) -> tuple[int, int] | None:
    match = re.match(r"(\d+)\.(\d+)", module.__version__ or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _admin_connection(psycopg: Any, dsn: str) -> Any:
    """Подключение к базе для CREATE/DROP DATABASE.

    Сначала пробуется база из самого DSN, затем стандартная ``postgres``
    (DSN в сообщениях об ошибках не раскрывается — в нём может быть пароль).
    """
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    candidates = []
    if params.get("dbname"):
        candidates.append(params["dbname"])
    candidates.append("postgres")
    errors = []
    for dbname in dict.fromkeys(candidates):
        admin_params = dict(params)
        admin_params["dbname"] = dbname
        try:
            return psycopg.connect(
                psycopg.conninfo.make_conninfo(**admin_params), autocommit=True
            )
        except Exception as error:
            errors.append(f"dbname={dbname!r}: {error}")
    raise RuntimeError(
        f"не удалось подключиться к PostgreSQL по {TEST_DSN_ENV} "
        f"(проверьте хост/порт/роль): {'; '.join(errors)}"
    )


def create_test_database(admin_dsn: str, *, dbname: str | None = None) -> tuple[str, str]:
    """Создаёт изолированную тестовую базу; возвращает (test_dsn, dbname).

    Роль из ``admin_dsn`` должна иметь право CREATEDB. Возвращённый DSN
    повторяет параметры исходного (хост, порт, роль, пароль), но указывает
    на созданную базу.
    """
    psycopg = _import_psycopg()
    name = dbname or f"{TEST_DB_PREFIX}{uuid.uuid4().hex[:8]}"
    with _admin_connection(psycopg, admin_dsn) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    psycopg.sql.SQL("CREATE DATABASE {}").format(
                        psycopg.sql.Identifier(name)
                    )
                )
            except psycopg.errors.InsufficientPrivilege as error:
                raise RuntimeError(
                    f"роль из {TEST_DSN_ENV} не имеет права CREATEDB — "
                    f"не удалось создать базу {name}"
                ) from error
    params = psycopg.conninfo.conninfo_to_dict(admin_dsn)
    params["dbname"] = name
    return psycopg.conninfo.make_conninfo(**params), name


def drop_test_database(admin_dsn: str, dbname: str) -> None:
    """Удаляет тестовую базу (WITH (FORCE) для отсечения зависших сессий)."""
    psycopg = _import_psycopg()
    with _admin_connection(psycopg, admin_dsn) as conn:
        with conn.cursor() as cur:
            drop_with_force = psycopg.sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                psycopg.sql.Identifier(dbname)
            )
            drop_plain = psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                psycopg.sql.Identifier(dbname)
            )
            try:
                cur.execute(drop_with_force)
            except psycopg.errors.SyntaxError:
                # PostgreSQL < 13 не поддерживает WITH (FORCE).
                cur.execute(drop_plain)


def apply_tasks_schema(connection: Any) -> list[str]:
    """Применяет миграции tasks-схемы; возвращает имена применённых файлов.

    Подключение должно быть в autocommit-режиме: файлы сами управляют
    транзакцией через ``BEGIN``/``COMMIT``. Весь файл выполняется одним
    вызовом — без параметров psycopg использует simple query protocol,
    который разрешает несколько операторов в одном запросе (в том числе
    ``$$``-тела функций с точками с запятой внутри).
    """
    if not SCHEMA_001.exists():
        raise FileNotFoundError(f"не найдена схема задач: {SCHEMA_001}")
    applied: list[str] = []
    for path in (SCHEMA_001, SCHEMA_002):
        if not path.exists():
            continue
        connection.execute(path.read_text(encoding="utf-8"))
        applied.append(path.name)
    return applied


def _sql_report_statuses() -> set[str]:
    """SQL-состояния promscan.reports из CHECK-ограничений миграций."""
    statuses = _parse_status_check(SCHEMA_001)
    assert statuses, f"в {SCHEMA_001.name} не найден CHECK статусов promscan.reports"
    if SCHEMA_002.exists():
        statuses |= _parse_status_check(SCHEMA_002) or {"rejected"}
    return statuses


def _parse_status_check(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"CHECK\s*\(\s*status\s+IN\s*\(([^)]*)\)", text, re.IGNORECASE)
    if not match:
        return set()
    return set(re.findall(r"'([a-z_]+)'", match.group(1)))


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tasks_dsn() -> str:
    dsn = os.getenv(TEST_DSN_ENV, "").strip()
    if not dsn:
        pytest.skip(
            f"переменная {TEST_DSN_ENV} не задана — "
            "интеграционные тесты PostgreSQL пропущены"
        )
    return dsn


@pytest.fixture(scope="session")
def psycopg(tasks_dsn):
    module = pytest.importorskip(
        "psycopg", reason="psycopg (>= 3.2) не установлен: pip install 'psycopg[binary]'"
    )
    version = _psycopg_version(module)
    if version is not None and version < (3, 2):
        pytest.skip(f"требуется psycopg >= 3.2, установлен {module.__version__}")
    return module


@pytest.fixture(scope="session")
def tasks_test_db(tasks_dsn, psycopg):
    """Изолированная тестовая база со схемой tasks (одна на сессию)."""
    test_dsn, dbname = create_test_database(tasks_dsn)
    try:
        with psycopg.connect(test_dsn, autocommit=True) as conn:
            apply_tasks_schema(conn)
        yield test_dsn
    finally:
        drop_test_database(tasks_dsn, dbname)


@pytest.fixture()
def reports_conn(tasks_test_db):
    """Соединение с тестовой базой; таблица promscan.reports очищена."""
    psycopg = _import_psycopg()
    with psycopg.connect(tasks_test_db, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE promscan.reports")
        yield conn


@pytest.fixture()
def storage_module(monkeypatch):
    """Импортирует app.services.storage без соединения с PostgreSQL.

    Модуль создаёт пул при импорте, но подключается лениво, поэтому
    достаточно любой непустой DSN в DATABASE_URL.
    """
    if not os.environ.get("DATABASE_URL", "").strip():
        monkeypatch.setenv("DATABASE_URL", _DUMMY_DSN)
    import app.services.storage as storage

    return storage


# ---------------------------------------------------------------------------
# Юнит-тесты: маппинг легаси-статусов на SQL-состояния (без PostgreSQL)
# ---------------------------------------------------------------------------


def test_legacy_status_mapping_matches_sql_states(storage_module):
    """Миграция легаси-статусов: pending → open, completed → closed.

    Значения маппинга — только SQL-состояния promscan.reports из
    database/sql/tasks; сами легаси-значения в SQL не протекают.
    """
    from app.schemas.report import RepairStatus

    legacy_to_db = storage_module.LEGACY_STATUS_TO_DB

    assert legacy_to_db[RepairStatus.PENDING] == "open"
    assert legacy_to_db[RepairStatus.IN_PROGRESS] == "in_progress"
    assert legacy_to_db[RepairStatus.COMPLETED] == "closed"
    assert legacy_to_db[RepairStatus.REJECTED] == "rejected"

    # маппинг покрывает весь легаси-перечень статусов без пропусков
    assert set(legacy_to_db) == set(RepairStatus)

    sql_values = set(legacy_to_db.values())
    # rejected допускается как расширение после 002-миграции
    allowed = _sql_report_statuses() | {"rejected"}
    assert sql_values <= allowed, f"статусы вне схемы: {sql_values - allowed}"
    # легаси-значения не должны попадать в promscan.reports как есть
    assert not sql_values & {"pending", "completed"}


def test_db_status_mapping_is_consistent_inverse(storage_module):
    """Обратный маппинг восстанавливает легаси-статусы из SQL-состояний."""
    from app.schemas.report import RepairStatus

    legacy_to_db = storage_module.LEGACY_STATUS_TO_DB
    db_to_legacy = storage_module.DB_STATUS_TO_LEGACY

    assert db_to_legacy == {value: status for status, value in legacy_to_db.items()}
    assert db_to_legacy["open"] == RepairStatus.PENDING
    assert db_to_legacy["closed"] == RepairStatus.COMPLETED
    # каждое базовое SQL-состояние читается обратно в легаси-контракт
    assert BASE_SQL_STATUSES <= set(db_to_legacy)


def test_task_row_to_report_returns_legacy_statuses(storage_module):
    """Функция чтения storage возвращает легаси-статусы для SQL-состояний."""
    from app.schemas.report import RepairStatus

    service = storage_module.StorageService(pool=object(), tasks_pool=object())
    base_row = {
        "id": uuid.uuid4(),
        "equipment_id": "pump-test-01",
        "inspection_id": "insp-test-01",
        "comment": "",
        "result": {},
        "photo_url": None,
        "started_at": None,
        "completed_at": None,
        "repair_comment": None,
        "created_at": datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc),
    }
    expectations = {
        "open": RepairStatus.PENDING,
        "in_progress": RepairStatus.IN_PROGRESS,
        "closed": RepairStatus.COMPLETED,
        "rejected": RepairStatus.REJECTED,
    }
    for db_status, expected in expectations.items():
        row = dict(base_row, status=db_status)
        report = service._task_row_to_report(row, "Насос тест")
        assert report.repair_status == expected, db_status


# ---------------------------------------------------------------------------
# Интеграционные тесты: жизненный цикл promscan.reports
# ---------------------------------------------------------------------------


def _dict_cursor(connection: Any) -> Any:
    from psycopg.rows import dict_row

    return connection.cursor(row_factory=dict_row)


def _insert_report(
    cur: Any,
    *,
    equipment_id: str = "pump-test-01",
    inspection_id: str = "insp-test-01",
    created_at: datetime | None = None,
) -> uuid.UUID:
    cur.execute(
        """
        INSERT INTO promscan.reports (equipment_id, inspection_id, result, created_at)
        VALUES (%s, %s, '{}'::jsonb, COALESCE(%s, clock_timestamp()))
        RETURNING id
        """,
        (equipment_id, inspection_id, created_at),
    )
    return cur.fetchone()["id"]


def _fetch_report(cur: Any, report_id: uuid.UUID) -> dict:
    cur.execute(
        f"SELECT {REPORT_COLUMNS} FROM promscan.reports WHERE id = %s",
        (report_id,),
    )
    row = cur.fetchone()
    assert row is not None, "задача исчезла из promscan.reports"
    return row


def _assign(
    cur: Any,
    report_id: uuid.UUID,
    *,
    full_name: str = "Сидоров Пётр Николаевич",
) -> None:
    cur.execute(
        """
        UPDATE promscan.reports
        SET assignee_id = %s, assignee_full_name = %s
        WHERE id = %s
        """,
        (uuid.uuid4(), full_name, report_id),
    )


def _set_status(cur: Any, report_id: uuid.UUID, status: str) -> None:
    cur.execute(
        "UPDATE promscan.reports SET status = %s WHERE id = %s",
        (status, report_id),
    )


def _prepare_report(cur: Any, status: str) -> uuid.UUID:
    """Приводит задачу в нужный статус валидной цепочкой переходов."""
    report_id = _insert_report(cur)
    if status == "open":
        return report_id
    _assign(cur, report_id)
    _set_status(cur, report_id, "in_progress")
    if status == "in_progress":
        return report_id
    assert status == "closed", f"неизвестный статус подготовки: {status}"
    _set_status(cur, report_id, "closed")
    return report_id


def test_new_report_is_created_only_in_open_state(reports_conn):
    """Новая задача создаётся только в open и без отметок жизненного цикла."""
    with _dict_cursor(reports_conn) as cur:
        report_id = _insert_report(cur)
        row = _fetch_report(cur, report_id)
        assert row["status"] == "open"
        assert row["started_at"] is None
        assert row["completed_at"] is None
        assert row["repair_comment"] is None
        assert row["assignee_id"] is None
        assert row["created_at"] is not None

        # явный 'open' при вставке тоже допускается
        cur.execute(
            """
            INSERT INTO promscan.reports (equipment_id, inspection_id, status, result)
            VALUES ('pump-test-01', 'insp-test-02', 'open', '{}'::jsonb)
            """
        )
        cur.execute("SELECT count(*) FROM promscan.reports")
        assert cur.fetchone()["count"] == 2


@pytest.mark.parametrize("initial_status", ["in_progress", "closed", "rejected"])
def test_report_cannot_be_created_in_non_open_state(
    reports_conn, psycopg, initial_status
):
    """Вставка сразу в рабочий/закрытый/отклонённый статус отклоняется."""
    with _dict_cursor(reports_conn) as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO promscan.reports (equipment_id, inspection_id, status, result)
                VALUES ('pump-test-01', 'insp-test-01', %s, '{}'::jsonb)
                """,
                (initial_status,),
            )
        cur.execute("SELECT count(*) FROM promscan.reports")
        assert cur.fetchone()["count"] == 0


def test_report_cannot_be_created_with_lifecycle_timestamps(reports_conn, psycopg):
    """Отметки started_at/completed_at нельзя проставить при вставке."""
    with _dict_cursor(reports_conn) as cur:
        for column in ("started_at", "completed_at"):
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute(
                    f"""
                    INSERT INTO promscan.reports (equipment_id, inspection_id, {column}, result)
                    VALUES ('pump-test-01', 'insp-test-01', clock_timestamp(), '{{}}'::jsonb)
                    """
                )
        cur.execute("SELECT count(*) FROM promscan.reports")
        assert cur.fetchone()["count"] == 0


def test_report_cannot_start_without_assignee(reports_conn, psycopg):
    """open → in_progress разрешён только назначенной задаче."""
    with _dict_cursor(reports_conn) as cur:
        report_id = _insert_report(cur)
        with pytest.raises(psycopg.errors.CheckViolation) as excinfo:
            _set_status(cur, report_id, "in_progress")
        assert "assign" in str(excinfo.value).lower()
        # неудачный UPDATE ничего не изменил — задача осталась open
        assert _fetch_report(cur, report_id)["status"] == "open"

        # после назначения исполнителя старт проходит
        _assign(cur, report_id)
        _set_status(cur, report_id, "in_progress")
        assert _fetch_report(cur, report_id)["status"] == "in_progress"


def test_trigger_sets_started_at_when_work_starts(reports_conn):
    """Триггер сам проставляет started_at при переходе в in_progress."""
    with _dict_cursor(reports_conn) as cur:
        report_id = _prepare_report(cur, "in_progress")
        row = _fetch_report(cur, report_id)
        assert row["status"] == "in_progress"
        assert row["started_at"] is not None
        assert row["completed_at"] is None
        assert row["repair_comment"] is None
        assert row["updated_at"] >= row["created_at"]


def test_in_progress_report_can_be_closed(reports_conn):
    """in_progress → closed закрывает задачу и проставляет completed_at."""
    with _dict_cursor(reports_conn) as cur:
        report_id = _prepare_report(cur, "in_progress")
        started_at = _fetch_report(cur, report_id)["started_at"]
        assert started_at is not None

        _set_status(cur, report_id, "closed")
        row = _fetch_report(cur, report_id)
        assert row["status"] == "closed"
        assert row["completed_at"] is not None
        assert row["completed_at"] >= started_at
        # снимок исполнителя сохранён
        assert row["assignee_full_name"] == "Сидоров Пётр Николаевич"


def test_open_report_can_be_rejected_with_repair_comment(reports_conn, psycopg):
    """open → rejected с repair_comment (после 002_rejected_status.sql).

    Миграция 002 требует назначенного исполнителя и непустую причину
    отказа; при отклонении из open отметки started_at/completed_at
    остаются пустыми (работа не начиналась и не завершалась).
    """
    comment = "Ложное срабатывание: дефект не подтверждён повторным осмотром"
    with _dict_cursor(reports_conn) as cur:
        report_id = _insert_report(cur)
        # 002: отклонить можно только назначенную задачу
        _assign(cur, report_id)
        try:
            cur.execute(
                """
                UPDATE promscan.reports
                SET status = 'rejected', repair_comment = %s
                WHERE id = %s
                """,
                (comment, report_id),
            )
        except psycopg.errors.CheckViolation:
            if not SCHEMA_002.exists():
                pytest.skip(
                    "database/sql/tasks/002_rejected_status.sql отсутствует — "
                    "схема не поддерживает статус 'rejected'"
                )
            raise
        row = _fetch_report(cur, report_id)
        assert row["status"] == "rejected"
        assert row["repair_comment"] == comment
        assert row["started_at"] is None
        assert row["completed_at"] is None

        # без причины отклонение не проходит (repair_comment обязателен)
        other_id = _insert_report(cur)
        _assign(cur, other_id)
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE promscan.reports SET status = 'rejected' WHERE id = %s",
                (other_id,),
            )
        assert _fetch_report(cur, other_id)["status"] == "open"


def test_in_progress_report_rejection_keeps_started_at(reports_conn, psycopg):
    """in_progress → rejected сохраняет started_at и требует причину."""
    comment = "Повторная диагностика: дефект классифицирован как ложный"
    with _dict_cursor(reports_conn) as cur:
        report_id = _prepare_report(cur, "in_progress")
        started_at = _fetch_report(cur, report_id)["started_at"]
        assert started_at is not None
        try:
            cur.execute(
                """
                UPDATE promscan.reports
                SET status = 'rejected', repair_comment = %s
                WHERE id = %s
                """,
                (comment, report_id),
            )
        except psycopg.errors.CheckViolation:
            if not SCHEMA_002.exists():
                pytest.skip(
                    "database/sql/tasks/002_rejected_status.sql отсутствует — "
                    "схема не поддерживает статус 'rejected'"
                )
            raise
        row = _fetch_report(cur, report_id)
        assert row["status"] == "rejected"
        assert row["repair_comment"] == comment
        assert row["started_at"] == started_at
        assert row["completed_at"] is None


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        ("open", "closed"),
        ("in_progress", "open"),
        ("closed", "open"),
        ("closed", "in_progress"),
        ("closed", "rejected"),
    ],
)
def test_invalid_status_transitions_fail(
    reports_conn, psycopg, from_status, to_status
):
    """Невалидные переходы отклоняются триггером, статус не меняется."""
    with _dict_cursor(reports_conn) as cur:
        report_id = _prepare_report(cur, from_status)
        with pytest.raises(psycopg.errors.CheckViolation):
            _set_status(cur, report_id, to_status)
        assert _fetch_report(cur, report_id)["status"] == from_status


def test_lifecycle_timestamps_cannot_be_set_manually(reports_conn, psycopg):
    """Прямая правка started_at/completed_at запрещена — ими управляет триггер."""
    with _dict_cursor(reports_conn) as cur:
        open_id = _insert_report(cur)
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE promscan.reports SET started_at = clock_timestamp() WHERE id = %s",
                (open_id,),
            )
        assert _fetch_report(cur, open_id)["started_at"] is None

        in_progress_id = _prepare_report(cur, "in_progress")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE promscan.reports SET completed_at = clock_timestamp() WHERE id = %s",
                (in_progress_id,),
            )
        assert _fetch_report(cur, in_progress_id)["completed_at"] is None


def test_assignee_snapshot_is_frozen_after_start(reports_conn, psycopg):
    """После начала работы снимок исполнителя менять нельзя."""
    with _dict_cursor(reports_conn) as cur:
        report_id = _prepare_report(cur, "in_progress")
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE promscan.reports SET assignee_full_name = %s WHERE id = %s",
                ("Другой Иванов", report_id),
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "UPDATE promscan.reports SET assignee_id = %s WHERE id = %s",
                (uuid.uuid4(), report_id),
            )
        assert (
            _fetch_report(cur, report_id)["assignee_full_name"]
            == "Сидоров Пётр Николаевич"
        )


def test_report_list_orders_by_created_at_desc(reports_conn):
    """Список задач выдаётся в порядке created_at DESC (как get_reports)."""
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    with _dict_cursor(reports_conn) as cur:
        _insert_report(cur, created_at=base)
        _insert_report(cur, created_at=base + timedelta(hours=1))
        newest_id = _insert_report(cur, created_at=base + timedelta(days=1))

        cur.execute("SELECT id, created_at FROM promscan.reports ORDER BY created_at DESC")
        rows = cur.fetchall()

    assert len(rows) == 3
    assert rows[0]["id"] == newest_id
    stamps = [row["created_at"] for row in rows]
    assert stamps == sorted(stamps, reverse=True)
