"""Catalog projection regressions using schema-aware, in-memory pools."""

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.storage import StorageService


SQL_SCHEMA = PROJECT_ROOT / "database" / "sql" / "001_schema.sql"
CORE_MIGRATION = PROJECT_ROOT / "database" / "migrations" / "001_core.sql"
WEBAPP_OVERLAY = PROJECT_ROOT / "database" / "migrations" / "005_webapp_catalog.sql"

TABLE_ALIASES = {
    "e": "promscan.equipment",
    "w": "promscan.webapp_equipment",
    "n": "promscan.equipment_nodes",
}


def _declared_columns(path: Path, table: str) -> set[str]:
    sql = path.read_text(encoding="utf-8")
    table_re = re.escape(table)
    create = re.search(
        rf"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table_re}\s*\((.*?)\n\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    columns: set[str] = set()
    if create:
        columns.update(
            re.findall(
                r"^\s{4}([a-z_][a-z0-9_]*)\s+(?=(?:text|date|integer|bigint|"
                r"double\s+precision|timestamptz|jsonb|char|boolean)\b)",
                create.group(1),
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )
    columns.update(
        re.findall(
            rf"ALTER\s+TABLE\s+{table_re}\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"
            r"([a-z_][a-z0-9_]*)\s+",
            sql,
            flags=re.IGNORECASE,
        )
    )
    return columns


def _schema_columns(schema_path: Path, table: str) -> set[str]:
    source = _declared_columns(schema_path, table)
    if table == "promscan.webapp_equipment":
        source |= _declared_columns(WEBAPP_OVERLAY, table)
    return source


def _component(**overrides):
    component = {
        "id": "node-rotor",
        "name": "Ротор",
        "type": "Вращающийся узел",
        "installation_date": "Не указана",
        "age_months": 0,
        "criticality_factor": 1.0,
    }
    component.update(overrides)
    return component


def _catalog_data():
    created = datetime(2024, 1, 2, tzinfo=timezone.utc)
    updated = datetime(2025, 3, 4, tzinfo=timezone.utc)
    equipment = [
        {
            "id": "pump-fallback",
            "name": "Насос из каталога",
            "serial_number": None,
            "inventory_number": "INV-42",
            "location": "Цех 7",
            "commissioned_at": date(2020, 6, 15),
            "state": "fault",
            "created_at": created,
            "updated_at": updated,
        },
        {
            "id": "pump-catalog-only",
            "name": "Насос без overlay",
            "serial_number": "SN-ONLY",
            "inventory_number": "INV-ONLY",
            "location": "Участок 2",
            "commissioned_at": None,
            "state": None,
            "created_at": created,
            "updated_at": updated,
        },
    ]
    overlay = [
        {
            "id": "pump-fallback",
            "name": "Имя из webapp",
            "serial_number": None,
            "location": None,
            "commissioned_at": None,
            "component_age": "6 лет",
            "last_maintenance_at": date(2025, 2, 1),
            "state": None,
            "components_json": [],
            "inspection_count": 3,
            "created_at": None,
            "updated_at": None,
        },
        {
            "id": "overlay-only",
            "name": "Только webapp",
            "serial_number": "WEB-7",
            "location": "Цех 9",
            "commissioned_at": date(2022, 7, 8),
            "component_age": "3 года",
            "last_maintenance_at": None,
            "state": "maintenance",
            "components_json": [_component(id="overlay-component", name="Подшипник")],
            "inspection_count": 1,
            "created_at": created,
            "updated_at": updated,
        },
    ]
    nodes = [
        {
            "id": "node-rotor",
            "equipment_id": "pump-fallback",
            "name": "Ротор",
            "description": "Вращающийся узел",
            "sort_order": 1,
        },
        {
            "id": "node-seal",
            "equipment_id": "pump-fallback",
            "name": "Уплотнение",
            "description": None,
            "sort_order": 2,
        },
        {
            "id": "node-only",
            "equipment_id": "pump-catalog-only",
            "name": "Корпус",
            "description": None,
            "sort_order": 1,
        },
    ]
    return equipment, overlay, nodes


class _FakeCursor:
    def __init__(self, pool):
        self.pool = pool
        self.rows = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.rows, self.row = self.pool.execute(query, params or ())

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class SchemaAwareCatalogPool:
    """Recognize only the equipment projection queries used by StorageService."""

    def __init__(self, schema_path, equipment=None, overlay=None, nodes=None):
        defaults = _catalog_data()
        self.schema_path = schema_path
        self.equipment = defaults[0] if equipment is None else equipment
        self.overlay = defaults[1] if overlay is None else overlay
        self.nodes = defaults[2] if nodes is None else nodes
        self.queries = []

    def cursor(self, **_kwargs):
        return _FakeCursor(self)

    def _check_query_columns(self, query):
        for alias, column in re.findall(r"\b([ewn])\.([a-z_][a-z0-9_]*)\b", query):
            table = TABLE_ALIASES[alias]
            columns = _schema_columns(self.schema_path, table)
            assert column in columns, (
                f"StorageService references {alias}.{column}, but {table} in "
                f"{self.schema_path.relative_to(PROJECT_ROOT)} declares "
                f"{sorted(columns)}"
            )

    @staticmethod
    def _date_text(value):
        if value is None:
            return "Не указана"
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    def _project(self, equipment, overlay):
        overlay_components = overlay.get("components_json") if overlay else None
        if overlay_components:
            components = overlay_components
        else:
            components = [
                {
                    "id": node["id"],
                    "name": node["name"],
                    "type": node["name"],
                    "installation_date": self._date_text(
                        equipment.get("commissioned_at") if equipment else None
                    ),
                    "age_months": 0,
                    "criticality_factor": 1.0,
                }
                for node in sorted(
                    (n for n in self.nodes if equipment and n["equipment_id"] == equipment["id"]),
                    key=lambda n: (n["sort_order"], n["id"]),
                )
            ]

        def coalesce(*values):
            return next((value for value in values if value is not None), None)

        return {
            "id": coalesce(overlay.get("id") if overlay else None, equipment.get("id") if equipment else None),
            "name": coalesce(overlay.get("name") if overlay else None, equipment.get("name") if equipment else None),
            "serial_number": coalesce(
                overlay.get("serial_number") if overlay else None,
                equipment.get("serial_number") if equipment else None,
                equipment.get("inventory_number") if equipment else None,
                equipment.get("id") if equipment else None,
            ),
            "location": coalesce(overlay.get("location") if overlay else None, equipment.get("location") if equipment else None),
            "commissioned_at": coalesce(
                overlay.get("commissioned_at") if overlay else None,
                equipment.get("commissioned_at") if equipment else None,
            ),
            "component_age": overlay.get("component_age") if overlay else None,
            "last_maintenance_at": overlay.get("last_maintenance_at") if overlay else None,
            "state": coalesce(overlay.get("state") if overlay else None, equipment.get("state") if equipment else None),
            "components_json": components,
            "inspection_count": (overlay or {}).get("inspection_count") or 0,
            "created_at": coalesce(overlay.get("created_at") if overlay else None, equipment.get("created_at") if equipment else None),
            "updated_at": coalesce(overlay.get("updated_at") if overlay else None, equipment.get("updated_at") if equipment else None),
        }

    def _joined_rows(self):
        equipment_by_id = {row["id"]: row for row in self.equipment}
        overlay_by_id = {row["id"]: row for row in self.overlay}
        all_ids = equipment_by_id.keys() | overlay_by_id.keys()
        return [
            self._project(equipment_by_id.get(equipment_id), overlay_by_id.get(equipment_id))
            for equipment_id in all_ids
        ]

    def execute(self, query, params):
        self.queries.append((query, params))
        normalized = " ".join(query.split())
        assert re.search(
            r"FROM promscan\.equipment AS e FULL OUTER JOIN "
            r"promscan\.webapp_equipment AS w ON w\.id = e\.id",
            normalized,
        ), f"Unexpected catalog query: {normalized}"
        assert "jsonb_array_length(COALESCE(w.components_json, '[]'::jsonb))" in normalized
        assert "FROM promscan.equipment_nodes AS n" in normalized
        self._check_query_columns(query)

        detail = re.search(r"WHERE COALESCE\(w\.id, e\.id\) = %s\s*$", normalized)
        if detail:
            assert len(params) == 1, f"Unexpected detail parameters: {params!r}"
            row = next((row for row in self._joined_rows() if row["id"] == params[0]), None)
            return [], row
        assert not params, f"Unexpected list parameters: {params!r}"
        assert re.search(r"ORDER BY COALESCE\(w\.name, e\.name\) ASC\s*$", normalized)
        return sorted(self._joined_rows(), key=lambda row: row["name"]), None


def _service(schema_path=CORE_MIGRATION, **pool_kwargs):
    return StorageService(pool=SchemaAwareCatalogPool(schema_path, **pool_kwargs), tasks_pool=object())


def test_get_all_projects_catalog_fallback_overlay_and_equipment_nodes():
    service = _service()

    equipment = {row.id: row for row in service.get_all_equipment()}

    fallback = equipment["pump-fallback"]
    assert fallback.name == "Имя из webapp"
    assert fallback.serial_number == "INV-42"
    assert fallback.location == "Цех 7"
    assert fallback.installation_date == "2020-06-15"
    assert fallback.status == "fault"
    assert fallback.component_age == "6 лет"
    assert fallback.last_maintenance_date == "2025-02-01"
    assert fallback.inspection_count == 3
    assert [component.model_dump() for component in fallback.components] == [
        _component(
            type="Ротор",
            installation_date="2020-06-15",
        ),
        _component(
            id="node-seal",
            name="Уплотнение",
            type="Уплотнение",
            installation_date="2020-06-15",
        ),
    ]

    catalog_only = equipment["pump-catalog-only"]
    assert catalog_only.serial_number == "SN-ONLY"
    assert catalog_only.location == "Участок 2"
    assert catalog_only.installation_date == "1970-01-01"
    assert catalog_only.status == "operational"
    assert catalog_only.last_maintenance_date == "1970-01-01"
    assert catalog_only.components[0].id == "node-only"

    overlay_only = equipment["overlay-only"]
    assert overlay_only.name == "Только webapp"
    assert overlay_only.location == "Цех 9"
    assert overlay_only.installation_date == "2022-07-08"
    assert overlay_only.status == "maintenance"
    assert [component.id for component in overlay_only.components] == ["overlay-component"]


def test_get_by_id_uses_the_same_fallback_projection_and_returns_none_for_unknown_id():
    service = _service()

    equipment = service.get_equipment_by_id("pump-fallback")

    assert equipment is not None
    assert equipment.location == "Цех 7"
    assert equipment.installation_date == "2020-06-15"
    assert equipment.status == "fault"
    assert [component.id for component in equipment.components] == ["node-rotor", "node-seal"]
    assert service.get_equipment_by_id("missing") is None


@pytest.mark.parametrize("method", ["get_all_equipment", "get_equipment_by_id"])
def test_projection_is_compatible_with_catalog_only_sql_schema(method):
    """The original SQL schema must expose every column referenced by the query."""
    service = _service(schema_path=SQL_SCHEMA)

    if method == "get_all_equipment":
        service.get_all_equipment()
    else:
        service.get_equipment_by_id("pump-fallback")


@pytest.mark.parametrize(
    "components_json",
    [
        [_component(id="jsonb-component", name="JSONB")],
        json.dumps([_component(id="text-component", name="JSON text")], ensure_ascii=False),
    ],
    ids=["native-jsonb-value", "serialized-json-text"],
)
def test_get_by_id_accepts_jsonb_native_values_and_serialized_json(components_json):
    equipment, overlay, nodes = _catalog_data()
    overlay[0]["components_json"] = components_json
    service = _service(equipment=equipment, overlay=overlay, nodes=nodes)

    result = service.get_equipment_by_id("pump-fallback")

    assert result is not None
    assert len(result.components) == 1
    assert result.components[0].id in {"jsonb-component", "text-component"}


def test_get_by_id_uses_safe_empty_components_for_malformed_component_json_text():
    equipment, overlay, nodes = _catalog_data()
    overlay[0]["components_json"] = "not-json"
    service = _service(equipment=equipment, overlay=overlay, nodes=nodes)

    result = service.get_equipment_by_id("pump-fallback")

    assert result is not None
    assert result.components == []
