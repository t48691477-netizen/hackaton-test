"""Хранилище оборудования и задач на PostgreSQL.

Каталог оборудования хранится в schema promscan базы DATABASE_URL
(таблицы equipment, equipment_specs, equipment_nodes, node_specs и
таблица inspection_count — см. database/migrations/001_webapp_catalog.sql).

Задачи веб-панели и Android хранятся в schema promscan базы
DATABASE_TASKS_URL: таблица reports (контракт /front/api, статусы
open/in_progress/closed, опционально rejected после 002-миграции).

Легаси-контракт /api/reports (статусы pending/in_progress/completed/rejected)
маппится на хранимые статусы: pending→open, completed→closed, rejected→rejected.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from app.schemas.equipment import ComponentSchema, EquipmentCreate, EquipmentResponse
from app.schemas.report import ReportCreate, ReportResponse, RepairStatus
from app.services.db import (
    DatabaseError,
    DatabaseNotConfigured,
    PostgresPool,
    pools,
)

# Маппинг легаси-статусов /api/reports на статусы таблицы promscan.reports.
LEGACY_STATUS_TO_DB = {
    RepairStatus.PENDING: "open",
    RepairStatus.IN_PROGRESS: "in_progress",
    RepairStatus.COMPLETED: "closed",
    RepairStatus.REJECTED: "rejected",
}
DB_STATUS_TO_LEGACY = {v: k for k, v in LEGACY_STATUS_TO_DB.items()}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

_INVALID_STATUS_TRANSITION = "invalid_report_transition"
_LEGACY_ASSIGNEE_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "promscan:legacy-system-assignee"))
_LEGACY_ASSIGNEE_NAME = "Бригада ТОиР"


class StorageService:
    def __init__(self, pool: Optional[PostgresPool] = None, tasks_pool: Optional[PostgresPool] = None):
        self.catalog = pool or pools.get("catalog")
        self.tasks = tasks_pool or pools.get("tasks")

    # ------------------------------------------------------------------
    # Каталог оборудования
    # ------------------------------------------------------------------

    @staticmethod
    def _components(value: Any) -> list[ComponentSchema]:
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError:
                # JSONB из PostgreSQL всегда валиден, но некоторые драйверы
                #/legacy-адаптеры могут вернуть испорченную строку. Не даём
                # одному каталожному объекту уронить весь список оборудования.
                return []
        if not isinstance(value, (list, tuple)):
            return []
        return [ComponentSchema(**component) for component in (value or [])]

    def _row_to_equipment(self, row: dict) -> EquipmentResponse:
        components = self._components(row.get("components_json"))
        return EquipmentResponse(
            id=row["id"],
            name=row["name"],
            serial_number=row.get("serial_number") or row["id"],
            location=row.get("location") or "—",
            installation_date=self._date_or_default(row.get("commissioned_at")),
            component_age=row.get("component_age") or "—",
            last_maintenance_date=self._date_or_default(row.get("last_maintenance_at")),
            status=self._legacy_status(row.get("state")),
            components=components,
            created_at=self._iso(row.get("created_at")),
            updated_at=self._iso(row.get("updated_at")),
            inspection_count=int(row.get("inspection_count") or 0),
        )

    @staticmethod
    def _date_or_default(value: Any) -> str:
        if value is None:
            return "1970-01-01"
        text = value.isoformat() if hasattr(value, "isoformat") else str(value)
        text = text[:10]
        return text if _DATE_RE.match(text) else "1970-01-01"

    @staticmethod
    def _legacy_status(state: Optional[str]) -> str:
        # Каталог хранит operational/maintenance/fault; легаси-поле status
        # свободное текстовое — сохраняем прямо, дефект на "fault".
        if state in ("operational", "maintenance", "fault"):
            return state
        return "operational"

    @staticmethod
    def _state(status: str) -> str:
        s = (status or "").lower()
        if any(k in s for k in ("fault", "неиспр", "авар")):
            return "fault"
        if any(k in s for k in ("maint", "обслуж", "ремонт")):
            return "maintenance"
        return "operational"

    @staticmethod
    def _iso(value: Any) -> str:
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        dt = value if isinstance(value, datetime) else value
        if hasattr(dt, "isoformat"):
            text = dt.isoformat()
        else:
            text = str(dt)
        if text.endswith("+00:00"):
            text = text[:-6] + "Z"
        return text

    def _fetch_equipment(self, cur, equipment_id: str) -> Optional[dict]:
        cur.execute(
            """
            SELECT COALESCE(w.id, e.id) AS id,
                   COALESCE(w.name, e.name) AS name,
                   COALESCE(w.serial_number, e.serial_number, e.inventory_number, e.id) AS serial_number,
                   COALESCE(w.location, e.location) AS location,
                   COALESCE(w.commissioned_at, e.commissioned_at) AS commissioned_at,
                   w.component_age,
                   w.last_maintenance_at,
                   COALESCE(w.state, e.state) AS state,
                   CASE WHEN jsonb_array_length(COALESCE(w.components_json, '[]'::jsonb)) > 0
                        THEN w.components_json
                        ELSE COALESCE((
                            SELECT jsonb_agg(jsonb_build_object(
                                'id', n.id,
                                'name', n.name,
                                'type', n.name,
                                'installation_date', COALESCE(e.commissioned_at::text, 'Не указана'),
                                'age_months', CASE WHEN e.commissioned_at IS NULL THEN 0
                                    ELSE GREATEST(0, (
                                        EXTRACT(YEAR FROM age(current_date, e.commissioned_at)) * 12
                                        + EXTRACT(MONTH FROM age(current_date, e.commissioned_at))
                                    )::integer) END,
                                'criticality_factor', 1.0
                            ) ORDER BY n.sort_order, n.id)
                            FROM promscan.equipment_nodes AS n
                            WHERE n.equipment_id = e.id
                        ), '[]'::jsonb)
                   END AS components_json,
                   COALESCE(w.inspection_count, 0) AS inspection_count,
                   COALESCE(w.created_at, e.created_at) AS created_at,
                   COALESCE(w.updated_at, e.updated_at) AS updated_at
            FROM promscan.equipment AS e
            FULL OUTER JOIN promscan.webapp_equipment AS w ON w.id = e.id
            WHERE COALESCE(w.id, e.id) = %s
            """,
            (equipment_id,),
        )
        return cur.fetchone()

    def get_all_equipment(self) -> List[EquipmentResponse]:
        with self.catalog.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(w.id, e.id) AS id,
                       COALESCE(w.name, e.name) AS name,
                       COALESCE(w.serial_number, e.serial_number, e.inventory_number, e.id) AS serial_number,
                       COALESCE(w.location, e.location) AS location,
                       COALESCE(w.commissioned_at, e.commissioned_at) AS commissioned_at,
                       w.component_age,
                       w.last_maintenance_at,
                       COALESCE(w.state, e.state) AS state,
                       CASE WHEN jsonb_array_length(COALESCE(w.components_json, '[]'::jsonb)) > 0
                            THEN w.components_json
                            ELSE COALESCE((
                                SELECT jsonb_agg(jsonb_build_object(
                                    'id', n.id,
                                    'name', n.name,
                                    'type', n.name,
                                    'installation_date', COALESCE(e.commissioned_at::text, 'Не указана'),
                                    'age_months', CASE WHEN e.commissioned_at IS NULL THEN 0
                                        ELSE GREATEST(0, (
                                            EXTRACT(YEAR FROM age(current_date, e.commissioned_at)) * 12
                                            + EXTRACT(MONTH FROM age(current_date, e.commissioned_at))
                                        )::integer) END,
                                    'criticality_factor', 1.0
                                ) ORDER BY n.sort_order, n.id)
                                FROM promscan.equipment_nodes AS n
                                WHERE n.equipment_id = e.id
                            ), '[]'::jsonb)
                       END AS components_json,
                       COALESCE(w.inspection_count, 0) AS inspection_count,
                       COALESCE(w.created_at, e.created_at) AS created_at,
                       COALESCE(w.updated_at, e.updated_at) AS updated_at
                FROM promscan.equipment AS e
                FULL OUTER JOIN promscan.webapp_equipment AS w ON w.id = e.id
                ORDER BY COALESCE(w.name, e.name) ASC
                """
            )
            rows = cur.fetchall()
        return [self._row_to_equipment(dict(r)) for r in rows]

    def get_equipment_by_id(self, equipment_id: str) -> Optional[EquipmentResponse]:
        with self.catalog.cursor() as cur:
            row = self._fetch_equipment(cur, equipment_id)
        return self._row_to_equipment(dict(row)) if row else None

    def save_equipment(self, data: EquipmentCreate) -> EquipmentResponse:
        eq_id = data.id or f"eq_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        comps_json = json.dumps(
            [c.model_dump() for c in data.components], ensure_ascii=False
        )
        commissioned = self._parse_date(data.installation_date)
        last_maint = self._parse_date(data.last_maintenance_date)

        with self.catalog.cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO promscan.webapp_equipment AS e (
                    id, name, serial_number, location, commissioned_at,
                    component_age, last_maintenance_at, state, components_json,
                    inspection_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    serial_number = EXCLUDED.serial_number,
                    location = EXCLUDED.location,
                    commissioned_at = EXCLUDED.commissioned_at,
                    component_age = EXCLUDED.component_age,
                    last_maintenance_at = EXCLUDED.last_maintenance_at,
                    state = EXCLUDED.state,
                    components_json = EXCLUDED.components_json,
                    e.updated_at = now()
                """,
                (
                    eq_id,
                    data.name,
                    data.serial_number,
                    data.location,
                    commissioned,
                    data.component_age,
                    last_maint,
                    self._state(data.status),
                    comps_json,
                ),
            )
            row = self._fetch_equipment(cur, eq_id)

        result = self._row_to_equipment(dict(row))
        # Легаси-контракт возвращает присланные поля, а не перечитанные.
        result.status = data.status
        result.installation_date = data.installation_date
        result.last_maintenance_date = data.last_maintenance_date
        result.component_age = data.component_age
        result.components = data.components
        return result

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        text = value[:10]
        return text if _DATE_RE.match(text) else None

    def increment_inspection_count(self, equipment_id: str) -> None:
        with self.catalog.cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO promscan.webapp_equipment AS w (
                    id, name, serial_number, location, commissioned_at, state,
                    inspection_count
                )
                SELECT id, name,
                       COALESCE(serial_number, inventory_number, id),
                       location, commissioned_at, state, 1
                FROM promscan.equipment
                WHERE id = %s
                ON CONFLICT (id) DO UPDATE SET
                    inspection_count = w.inspection_count + 1,
                    updated_at = now()
                """,
                (equipment_id,),
            )
            if cur.rowcount == 0:
                cur.execute(
                    """
                    UPDATE promscan.webapp_equipment
                    SET inspection_count = inspection_count + 1, updated_at = now()
                    WHERE id = %s
                    """,
                    (equipment_id,),
                )

    def get_employee_full_name(self, employee_id: Optional[str]) -> Optional[str]:
        if not employee_id:
            return None
        try:
            uuid.UUID(str(employee_id))
        except (ValueError, TypeError, AttributeError):
            return None
        with self.employees_pool.cursor() as cur:
            cur.execute(
                """
                SELECT full_name FROM promscan.employees
                WHERE id = %s AND is_active
                """,
                (employee_id,),
            )
            row = cur.fetchone()
        return row["full_name"] if row else None

    @property
    def employees_pool(self) -> PostgresPool:
        try:
            return pools.get("employees")
        except DatabaseNotConfigured:
            raise

    # ------------------------------------------------------------------
    # Задачи (promscan.reports в DATABASE_TASKS_URL)
    # ------------------------------------------------------------------

    def _task_row_to_report(self, row: dict, equipment_name: str) -> ReportResponse:
        db_status = row.get("status") or "open"
        legacy = DB_STATUS_TO_LEGACY.get(db_status, RepairStatus.PENDING)
        result = row.get("result") or {}
        defects = result.get("defects", [])
        opinion = result.get("expert_opinion") or result.get("llm") or {
            "criticality": "low",
            "probable_cause": "",
            "recommendations": [],
        }
        return ReportResponse(
            id=str(row["id"]),
            equipment_id=row["equipment_id"],
            equipment_name=equipment_name or row["equipment_id"],
            created_at=self._iso(row.get("created_at")),
            repair_status=legacy,
            dispatcher_notes=row.get("comment") or "",
            defects_count=len(defects),
            defects=defects,
            expert_opinion=opinion,
            photo_url=row.get("photo_url") or "/static/uploads/placeholder.jpg",
            final_photo_url=result.get("final_photo_url"),
            started_at=self._iso(row.get("started_at")) if row.get("started_at") else None,
            completed_at=self._iso(row.get("completed_at")) if row.get("completed_at") else None,
            updated_at=self._iso(row.get("updated_at")),
        )

    def create_report(self, report_in: ReportCreate) -> ReportResponse:
        db_status = LEGACY_STATUS_TO_DB[report_in.repair_status]
        if db_status != "open":
            # Триггер схемы требует создавать задачи только в open;
            # легаси-статусы in_progress/completed/rejected достигаются
            # последующими переходами, но для совместимости API принимаем
            # исходный статус и выполняем переход сразу после вставки.
            pass
        inspection_id = f"insp-{uuid.uuid4().hex[:10]}"
        result = {
            "defects": [d.model_dump() for d in report_in.defects],
            "expert_opinion": report_in.expert_opinion.model_dump(),
            "photo_url": report_in.photo_url,
            "final_photo_url": report_in.final_photo_url,
        }
        equipment = self.get_equipment_by_id(report_in.equipment_id)
        if equipment is None:
            raise ValueError(f"Equipment '{report_in.equipment_id}' not found")

        with self.tasks.cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO promscan.reports (
                    equipment_id, inspection_id, status, comment, photo_url, result
                ) VALUES (%s, %s, 'open', %s, %s, %s)
                RETURNING id, equipment_id, inspection_id, status, comment,
                          photo_url, result, started_at, completed_at,
                          repair_comment, created_at, updated_at
                """,
                (
                    report_in.equipment_id,
                    inspection_id,
                    report_in.dispatcher_notes or "",
                    report_in.photo_url,
                    json.dumps(result),
                ),
            )
            row = dict(cur.fetchone())
            if db_status != "open":
                row = self._apply_legacy_initial_status(cur, row, db_status)

        return self._task_row_to_report(row, equipment.name)

    def _apply_legacy_initial_status(self, cur, row: dict, db_status: str) -> dict:
        """Легаси API допускал создание акта сразу в in_progress/completed/rejected.

        Схема задач разрешает вставку только в open, поэтому выполняем
        допустимую цепочку переходов сразу после вставки. Для rejected
        требуется причина — используем dispatcher_notes или заглушку.
        """
        current = row["status"]
        target = db_status
        chain: List[str] = []
        if current == "open":
            if target == "in_progress":
                chain = ["in_progress"]
            elif target == "closed":
                chain = ["in_progress", "closed"]
            elif target == "rejected":
                chain = ["rejected"]
        for nxt in chain:
            cur.execute(
                "SELECT assignee_id FROM promscan.reports WHERE id = %s",
                (row["id"],),
            )
            assignee_id = cur.fetchone()["assignee_id"]
            if nxt in ("in_progress", "rejected") and assignee_id is None:
                # Триггер требует назначенного сотрудника; снимок может быть
                # пустым только в легаси-режиме без assignee — ставим снимок
                # «Бригада ТОиР», чтобы не нарушать ограничение схемы.
                cur.execute(
                    """
                    UPDATE promscan.reports
                    SET assignee_id = %s, assignee_full_name = %s
                    WHERE id = %s
                    """,
                    (_LEGACY_ASSIGNEE_ID, _LEGACY_ASSIGNEE_NAME, row["id"]),
                )
            cur.execute(
                """
                UPDATE promscan.reports
                SET status = %s,
                    repair_comment = CASE WHEN %s = 'rejected'
                        THEN COALESCE(
                            NULLIF(btrim(%s), ''), repair_comment,
                            'Отклонено при создании (легаси-контракт)'
                        )
                        ELSE repair_comment END
                WHERE id = %s
                RETURNING id, equipment_id, inspection_id, status, comment,
                          photo_url, result, started_at, completed_at,
                          repair_comment, created_at, updated_at
                """,
                (nxt, nxt, row.get("comment"), row["id"]),
            )
            row = dict(cur.fetchone())
        return row

    def get_report(self, report_id: str) -> Optional[ReportResponse]:
        try:
            report_id = str(uuid.UUID(report_id))
        except (ValueError, TypeError, AttributeError):
            return None
        with self.tasks.cursor() as cur:
            row = self._fetch_task(cur, report_id)
        if row is None:
            return None
        equipment_name = self._equipment_name(row["equipment_id"])
        return self._task_row_to_report(row, equipment_name)

    def _fetch_task(self, cur, report_id: str) -> Optional[dict]:
        cur.execute(
            """
            SELECT id, equipment_id, inspection_id, status, comment, photo_url,
                   result, assignee_id, assignee_full_name, started_at,
                   completed_at, repair_comment, created_at, updated_at
            FROM promscan.reports
            WHERE id = %s
            """,
            (report_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def _equipment_names(self, equipment_ids: list[str]) -> dict[str, str]:
        if not equipment_ids:
            return {}
        # Catalog and tasks are separate physical databases; never query the
        # equipment schema through the tasks connection.
        with self.catalog.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM promscan.equipment WHERE id = ANY(%s)",
                (equipment_ids,),
            )
            names = {row["id"]: row["name"] for row in cur.fetchall()}
            cur.execute(
                "SELECT id, name FROM promscan.webapp_equipment WHERE id = ANY(%s)",
                (equipment_ids,),
            )
            names.update({row["id"]: row["name"] for row in cur.fetchall()})
        return names

    def _equipment_name(self, equipment_id: str) -> str:
        return self._equipment_names([equipment_id]).get(equipment_id, equipment_id)

    def get_reports(
        self,
        repair_status: Optional[RepairStatus] = None,
        equipment_id: Optional[str] = None,
    ) -> List[ReportResponse]:
        query = """
            SELECT id, equipment_id, inspection_id, status, comment, photo_url,
                   result, assignee_id, assignee_full_name, started_at,
                   completed_at, repair_comment, created_at, updated_at
            FROM promscan.reports WHERE 1=1
        """
        params: List[Any] = []
        if repair_status is not None:
            value = (
                repair_status.value
                if hasattr(repair_status, "value")
                else str(repair_status)
            )
            query += " AND status = %s"
            params.append(LEGACY_STATUS_TO_DB.get(RepairStatus(value), value))
        if equipment_id:
            query += " AND equipment_id = %s"
            params.append(equipment_id)
        query += " ORDER BY created_at DESC"

        with self.tasks.cursor() as tcur:
            tcur.execute(query, tuple(params))
            rows = [dict(r) for r in tcur.fetchall()]
        equipment_ids = list(dict.fromkeys(r["equipment_id"] for r in rows))
        names = self._equipment_names(equipment_ids)
        return [self._task_row_to_report(r, names.get(r["equipment_id"])) for r in rows]

    def update_report_status(
        self,
        report_id: str,
        new_status: RepairStatus,
        dispatcher_notes: Optional[str] = None,
    ) -> Optional[ReportResponse]:
        try:
            report_id = str(uuid.UUID(report_id))
        except (ValueError, TypeError, AttributeError):
            return None
        target = LEGACY_STATUS_TO_DB[new_status]
        with self.tasks.cursor(commit=True) as cur:
            row = self._fetch_task(cur, report_id)
            if row is None:
                return None
            current = row["status"]
            if current == target:
                if dispatcher_notes is not None and dispatcher_notes != (row.get("comment") or ""):
                    cur.execute(
                        "UPDATE promscan.reports SET comment = %s WHERE id = %s RETURNING *",
                        (dispatcher_notes, report_id),
                    )
                    row = dict(cur.fetchone())
                equipment_name = self._equipment_name(row["equipment_id"])
                return self._task_row_to_report(row, equipment_name)

            allowed_transitions = {
                "open": {"in_progress", "closed", "rejected"},
                "in_progress": {"closed", "rejected"},
                "closed": set(),
                "rejected": set(),
            }
            if target not in allowed_transitions.get(current, set()):
                raise ValueError(
                    f"Cannot transition report from {current} to {target}"
                )

            if target == "rejected":
                if row["assignee_id"] is None:
                    cur.execute(
                        """
                        UPDATE promscan.reports
                        SET assignee_id = %s, assignee_full_name = %s
                        WHERE id = %s
                        """,
                        (_LEGACY_ASSIGNEE_ID, _LEGACY_ASSIGNEE_NAME, report_id),
                    )
                cur.execute(
                    """
                    UPDATE promscan.reports
                    SET status = 'rejected',
                        comment = COALESCE(%s, comment),
                        repair_comment = COALESCE(
                            NULLIF(btrim(%s), ''), repair_comment,
                            'Отклонено диспетчером (легаси-контракт)'
                        )
                    WHERE id = %s
                    RETURNING id, equipment_id, inspection_id, status, comment,
                              photo_url, result, assignee_id, assignee_full_name,
                              started_at, completed_at, repair_comment,
                              created_at, updated_at
                    """,
                    (dispatcher_notes, dispatcher_notes, report_id),
                )
                updated = cur.fetchone()
                if updated is None:
                    raise ValueError(_INVALID_STATUS_TRANSITION)
                row = dict(updated)
            else:
                # Прямые переходы open→closed запрещены триггером; легаси
                # разрешал pending→completed, поэтому проходим через
                # in_progress отдельными UPDATE в одной транзакции.
                chain = [target]
                if current == "open" and target == "closed":
                    chain = ["in_progress", "closed"]
                if current == "open" and target == "in_progress" and row["assignee_id"] is None:
                    cur.execute(
                        """
                        UPDATE promscan.reports
                        SET assignee_id = %s, assignee_full_name = %s
                        WHERE id = %s
                        """,
                        (_LEGACY_ASSIGNEE_ID, _LEGACY_ASSIGNEE_NAME, report_id),
                    )
                if current == "open" and target == "closed" and row["assignee_id"] is None:
                    cur.execute(
                        """
                        UPDATE promscan.reports
                        SET assignee_id = %s, assignee_full_name = %s
                        WHERE id = %s
                        """,
                        (_LEGACY_ASSIGNEE_ID, _LEGACY_ASSIGNEE_NAME, report_id),
                    )
                for nxt in chain:
                    cur.execute(
                        """
                        UPDATE promscan.reports
                        SET status = %s,
                            comment = COALESCE(%s, comment)
                        WHERE id = %s
                        RETURNING id, equipment_id, inspection_id, status, comment,
                                  photo_url, result, assignee_id, assignee_full_name,
                                  started_at, completed_at, repair_comment,
                                  created_at, updated_at
                        """,
                        (nxt, dispatcher_notes, report_id),
                    )
                    updated = cur.fetchone()
                    if updated is None:
                        raise ValueError(_INVALID_STATUS_TRANSITION)
                    row = dict(updated)
            equipment_name = self._equipment_name(row["equipment_id"])
        return self._task_row_to_report(row, equipment_name)


import logging

logger = logging.getLogger("toir_storage")

# Ленивая инициализация singleton: DSN могут быть заданы после импорта
# (тесты выставляют переменные окружения в fixtures), а приложение без DSN
# должно импортироваться для /health и генерации OpenAPI.
_storage_service: Optional["StorageService"] = None


def get_storage() -> Optional["StorageService"]:
    """Ленивый singleton с повторной попыткой: возвращает None, пока DSN не задан.

    Роутеры обязаны проверять результат (helper `require_storage_dep` в
    app/routers/_deps.py поднимает 503). Повторная попытка нужна тестам,
    которые выставляют DATABASE_* после первого обращения.
    """
    global _storage_service
    if _storage_service is None:
        try:
            _storage_service = StorageService()
        except DatabaseNotConfigured:
            return None
    return _storage_service


def _create_default_storage() -> Optional["StorageService"]:
    try:
        svc = StorageService()
        logger.info("Хранилище PostgreSQL инициализировано")
        return svc
    except DatabaseNotConfigured:
        logger.warning(
            "DATABASE_URL не задан: хранилище не инициализировано "
            "(endpoints каталога/задач вернут 503 до настройки DSN)"
        )
        return None


storage_service: Optional["StorageService"] = _create_default_storage()
