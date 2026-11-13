import json
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.config import settings
from app.schemas.equipment import EquipmentCreate, EquipmentResponse, ComponentSchema
from app.schemas.report import ReportCreate, ReportResponse, RepairStatus
from app.schemas.defect import DefectItem
from app.schemas.inspection import LLMRecommendation

class StorageService:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        self._seed_initial_data()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS equipment (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        serial_number TEXT NOT NULL,
                        location TEXT NOT NULL,
                        installation_date TEXT NOT NULL,
                        component_age TEXT NOT NULL,
                        last_maintenance_date TEXT NOT NULL,
                        status TEXT NOT NULL,
                        components_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        inspection_count INTEGER DEFAULT 0
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reports (
                        id TEXT PRIMARY KEY,
                        equipment_id TEXT NOT NULL,
                        equipment_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        repair_status TEXT NOT NULL,
                        dispatcher_notes TEXT,
                        defects_count INTEGER NOT NULL,
                        defects_json TEXT NOT NULL,
                        expert_opinion_json TEXT NOT NULL,
                        photo_url TEXT NOT NULL,
                        final_photo_url TEXT
                    )
                """)
                conn.commit()

    def _seed_initial_data(self):
        """Создает начальный список оборудования, если база пуста."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM equipment")
                count = cursor.fetchone()[0]
                if count == 0:
                    sample_equipment = [
                        EquipmentCreate(
                            id="pump_d1250_03",
                            name="Центробежный сетевой насос 1Д1250-125",
                            serial_number="SN-1D-2018-0941",
                            location="Цех №3, Насосная станция технической воды",
                            installation_date="2018-05-20",
                            component_age="6 лет 6 месяцев",
                            last_maintenance_date="2026-04-10",
                            status="operational",
                            components=[
                                ComponentSchema(
                                    id="comp_rotor_01",
                                    name="Рабочее колесо насоса (двусторонний вход)",
                                    type="Вращающийся гидродинамический узел",
                                    installation_date="2018-05-20",
                                    age_months=78,
                                    criticality_factor=1.8
                                ),
                                ComponentSchema(
                                    id="comp_casing_02",
                                    name="Чугунный спиральный корпус и напорный патрубок",
                                    type="Статический напорный корпус",
                                    installation_date="2018-05-20",
                                    age_months=78,
                                    criticality_factor=1.4
                                ),
                                ComponentSchema(
                                    id="comp_weld_flange_03",
                                    name="Сварное фланцевое соединение всасывающей линии DN500",
                                    type="Сварной стык трубопровода",
                                    installation_date="2022-09-15",
                                    age_months=26,
                                    criticality_factor=1.6
                                )
                            ]
                        ),
                        EquipmentCreate(
                            id="compressor_k500_01",
                            name="Компрессор центробежный К-500-61-1",
                            serial_number="SN-K500-2020-003",
                            location="Цех компрессии воздуха №1",
                            installation_date="2020-08-14",
                            component_age="4 года 3 месяца",
                            last_maintenance_date="2026-08-15",
                            status="operational",
                            components=[
                                ComponentSchema(
                                    id="comp_diffuser_01",
                                    name="Лопаточный диффузор 2-й ступени",
                                    type="Проточная часть компрессора",
                                    installation_date="2020-08-14",
                                    age_months=51,
                                    criticality_factor=1.9
                                ),
                                ComponentSchema(
                                    id="comp_intercooler_02",
                                    name="Промежуточный трубчатый газоохладитель",
                                    type="Теплообменный узел",
                                    installation_date="2020-08-14",
                                    age_months=51,
                                    criticality_factor=1.3
                                )
                            ]
                        )
                    ]
                    for item in sample_equipment:
                        now_str = datetime.now().isoformat()
                        cursor.execute("""
                            INSERT INTO equipment (
                                id, name, serial_number, location, installation_date,
                                component_age, last_maintenance_date, status,
                                components_json, created_at, updated_at, inspection_count
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            item.id,
                            item.name,
                            item.serial_number,
                            item.location,
                            item.installation_date,
                            item.component_age,
                            item.last_maintenance_date,
                            item.status,
                            json.dumps([c.model_dump() for c in item.components], ensure_ascii=False),
                            now_str,
                            now_str,
                            0
                        ))
                    conn.commit()

    def get_all_equipment(self) -> List[EquipmentResponse]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM equipment ORDER BY name ASC")
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    comps_raw = json.loads(r["components_json"])
                    comps = [ComponentSchema(**c) for c in comps_raw]
                    results.append(EquipmentResponse(
                        id=r["id"],
                        name=r["name"],
                        serial_number=r["serial_number"],
                        location=r["location"],
                        installation_date=r["installation_date"],
                        component_age=r["component_age"],
                        last_maintenance_date=r["last_maintenance_date"],
                        status=r["status"],
                        components=comps,
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        inspection_count=r["inspection_count"]
                    ))
                return results

    def get_equipment_by_id(self, equipment_id: str) -> Optional[EquipmentResponse]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM equipment WHERE id = ?", (equipment_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                comps_raw = json.loads(row["components_json"])
                comps = [ComponentSchema(**c) for c in comps_raw]
                return EquipmentResponse(
                    id=row["id"],
                    name=row["name"],
                    serial_number=row["serial_number"],
                    location=row["location"],
                    installation_date=row["installation_date"],
                    component_age=row["component_age"],
                    last_maintenance_date=row["last_maintenance_date"],
                    status=row["status"],
                    components=comps,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    inspection_count=row["inspection_count"]
                )

    def save_equipment(self, data: EquipmentCreate) -> EquipmentResponse:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                eq_id = data.id or f"eq_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                now_str = datetime.now().isoformat()
                cursor.execute("SELECT id, created_at, inspection_count FROM equipment WHERE id = ?", (eq_id,))
                existing = cursor.fetchone()

                comps_json = json.dumps([c.model_dump() for c in data.components], ensure_ascii=False)

                if existing:
                    created_at = existing["created_at"]
                    inspection_count = existing["inspection_count"]
                    cursor.execute("""
                        UPDATE equipment SET
                            name = ?,
                            serial_number = ?,
                            location = ?,
                            installation_date = ?,
                            component_age = ?,
                            last_maintenance_date = ?,
                            status = ?,
                            components_json = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        data.name,
                        data.serial_number,
                        data.location,
                        data.installation_date,
                        data.component_age,
                        data.last_maintenance_date,
                        data.status,
                        comps_json,
                        now_str,
                        eq_id
                    ))
                else:
                    created_at = now_str
                    inspection_count = 0
                    cursor.execute("""
                        INSERT INTO equipment (
                            id, name, serial_number, location, installation_date,
                            component_age, last_maintenance_date, status,
                            components_json, created_at, updated_at, inspection_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        eq_id,
                        data.name,
                        data.serial_number,
                        data.location,
                        data.installation_date,
                        data.component_age,
                        data.last_maintenance_date,
                        data.status,
                        comps_json,
                        created_at,
                        now_str,
                        inspection_count
                    ))
                conn.commit()

                return EquipmentResponse(
                    id=eq_id,
                    name=data.name,
                    serial_number=data.serial_number,
                    location=data.location,
                    installation_date=data.installation_date,
                    component_age=data.component_age,
                    last_maintenance_date=data.last_maintenance_date,
                    status=data.status,
                    components=data.components,
                    created_at=created_at,
                    updated_at=now_str,
                    inspection_count=inspection_count
                )

    def increment_inspection_count(self, equipment_id: str):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE equipment SET inspection_count = inspection_count + 1 WHERE id = ?", 
                    (equipment_id,)
                )
                conn.commit()

    def create_report(self, report_in: ReportCreate) -> ReportResponse:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                report_id = f"act_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                now_str = datetime.now().isoformat()

                # Получаем имя оборудования
                cursor.execute("SELECT name FROM equipment WHERE id = ?", (report_in.equipment_id,))
                eq_row = cursor.fetchone()
                eq_name = eq_row["name"] if eq_row else f"Агрегат {report_in.equipment_id}"

                defects_json = json.dumps([d.model_dump() for d in report_in.defects], ensure_ascii=False)
                expert_json = json.dumps(report_in.expert_opinion.model_dump(), ensure_ascii=False)

                cursor.execute("""
                    INSERT INTO reports (
                        id, equipment_id, equipment_name, created_at, repair_status,
                        dispatcher_notes, defects_count, defects_json, expert_opinion_json,
                        photo_url, final_photo_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id,
                    report_in.equipment_id,
                    eq_name,
                    now_str,
                    report_in.repair_status.value,
                    report_in.dispatcher_notes or "",
                    len(report_in.defects),
                    defects_json,
                    expert_json,
                    report_in.photo_url,
                    report_in.final_photo_url
                ))
                conn.commit()

                return ReportResponse(
                    id=report_id,
                    equipment_id=report_in.equipment_id,
                    equipment_name=eq_name,
                    created_at=now_str,
                    repair_status=report_in.repair_status,
                    dispatcher_notes=report_in.dispatcher_notes or "",
                    defects_count=len(report_in.defects),
                    defects=report_in.defects,
                    expert_opinion=report_in.expert_opinion,
                    photo_url=report_in.photo_url,
                    final_photo_url=report_in.final_photo_url
                )

    def get_reports(
        self, 
        repair_status: Optional[RepairStatus] = None, 
        equipment_id: Optional[str] = None
    ) -> List[ReportResponse]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM reports WHERE 1=1"
                params: List[Any] = []
                if repair_status and hasattr(repair_status, "value"):
                    query += " AND repair_status = ?"
                    params.append(repair_status.value)
                elif repair_status and isinstance(repair_status, str):
                    query += " AND repair_status = ?"
                    params.append(repair_status)
                if equipment_id and isinstance(equipment_id, str):
                    query += " AND equipment_id = ?"
                    params.append(equipment_id)
                query += " ORDER BY created_at DESC"

                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    defects = [DefectItem(**d) for d in json.loads(r["defects_json"])]
                    expert = LLMRecommendation(**json.loads(r["expert_opinion_json"]))
                    results.append(ReportResponse(
                        id=r["id"],
                        equipment_id=r["equipment_id"],
                        equipment_name=r["equipment_name"],
                        created_at=r["created_at"],
                        repair_status=RepairStatus(r["repair_status"]),
                        dispatcher_notes=r["dispatcher_notes"] or "",
                        defects_count=r["defects_count"],
                        defects=defects,
                        expert_opinion=expert,
                        photo_url=r["photo_url"],
                        final_photo_url=r["final_photo_url"]
                    ))
                return results

storage_service = StorageService(settings.DB_PATH)
