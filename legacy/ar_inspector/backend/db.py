"""Small PostgreSQL adapter used by the stdlib HTTP backend.

The application intentionally has no ORM dependency.  The adapter supports
both psycopg 3 and psycopg2, keeps connection details in ``DATABASE_URL``, and
does not expose credentials in errors returned by the HTTP layer.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator


class DatabaseError(RuntimeError):
    """An expected database/configuration failure safe to report generically."""


class RepositoryNotFound(DatabaseError):
    """A requested persistent entity does not exist."""


class RepositoryConflict(DatabaseError):
    """The same idempotency key was used with a different request."""


class DatabaseNotConfigured(DatabaseError):
    pass


def _driver():
    """Return (module, major version) without importing a driver in mock mode."""
    try:
        import psycopg  # type: ignore

        return psycopg, 3
    except ImportError:
        try:
            import psycopg2  # type: ignore

            return psycopg2, 2
        except ImportError as error:
            raise DatabaseError(
                "PostgreSQL driver is not installed; install psycopg[binary] or psycopg2-binary"
            ) from error


class Database:
    """Thread-safe, bounded PostgreSQL connection provider.

    ``psycopg_pool``/``psycopg2.pool`` are used when available.  The fallback
    opens one short-lived connection per operation, which keeps local installs
    functional without silently introducing an in-memory store.
    """

    def __init__(self, dsn: str | None = None):
        self.dsn = (dsn or os.getenv("DATABASE_URL") or "").strip()
        if not self.dsn:
            raise DatabaseNotConfigured("DATABASE_URL is required for production profile")
        try:
            self.pool_size = max(1, int(os.getenv("DB_POOL_SIZE") or "5"))
        except ValueError as error:
            raise DatabaseError("DB_POOL_SIZE must be an integer") from error
        self._module, self._major = _driver()
        self._pool = None
        self._pool_lock = threading.Lock()

    def _ensure_pool(self):
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
            if self._pool is not None:
                return self._pool
            try:
                if self._major == 3:
                    try:
                        from psycopg_pool import ConnectionPool  # type: ignore
                    except ImportError:
                        ConnectionPool = None
                    if ConnectionPool is not None:
                        self._pool = ConnectionPool(
                            conninfo=self.dsn,
                            min_size=1,
                            max_size=self.pool_size,
                            open=True,
                        )
                else:
                    from psycopg2.pool import ThreadedConnectionPool  # type: ignore

                    self._pool = ThreadedConnectionPool(1, self.pool_size, self.dsn)
            except Exception as error:
                raise DatabaseError("could not initialize PostgreSQL connection pool") from error
        return self._pool

    def _connect(self):
        try:
            if self._major == 3:
                return self._module.connect(self.dsn)
            return self._module.connect(self.dsn)
        except Exception as error:
            raise DatabaseError("could not connect to PostgreSQL") from error

    @contextlib.contextmanager
    def connection(self) -> Iterator[Any]:
        pool = self._ensure_pool()
        pooled = pool is not None
        connection = None
        try:
            if self._major == 3 and pooled and hasattr(pool, "connection"):
                # psycopg_pool's context manager returns and safely puts back a
                # connection after commit/rollback.
                with pool.connection() as connection:
                    yield connection
                return
            if self._major == 2 and pooled:
                connection = pool.getconn()
            else:
                connection = self._connect()
            yield connection
            connection.commit()
        except DatabaseError:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise
        except Exception as error:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise DatabaseError("PostgreSQL operation failed") from error
        finally:
            if connection is not None:
                if self._major == 2 and pooled:
                    try:
                        pool.putconn(connection)
                    except Exception:
                        pass
                elif not pooled:
                    try:
                        connection.close()
                    except Exception:
                        pass

    @contextlib.contextmanager
    def cursor(self, connection: Any) -> Iterator[Any]:
        if self._major == 3:
            try:
                from psycopg.rows import dict_row  # type: ignore

                with connection.cursor(row_factory=dict_row) as cursor:
                    yield cursor
                return
            except ImportError:
                pass
        try:
            from psycopg2.extras import RealDictCursor  # type: ignore

            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
        except ImportError:
            with connection.cursor() as cursor:
                yield cursor

    def ping(self) -> None:
        with self.connection() as connection:
            with self.cursor(connection) as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    def check_schema(self) -> None:
        required = [
            "promscan.equipment",
            "promscan.equipment_nodes",
            "promscan.equipment_aliases",
            "promscan.equipment_specs",
            "promscan.equipment_components",
            "promscan.equipment_component_specs",
            "promscan.equipment_documents",
            "promscan_api.object_metadata",
            "promscan_api.inspections",
            "promscan_api.defects",
            "promscan_api.defect_resolutions",
            "promscan_api.defect_resolution_history",
            "promscan_api.reports",
        ]
        with self.connection() as connection:
            with self.cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT relation_name
                    FROM unnest(%s::text[]) AS expected(relation_name)
                    WHERE to_regclass(relation_name) IS NULL
                    """,
                    (required,),
                )
                missing = [dict(row)["relation_name"] for row in cursor.fetchall()]
        if missing:
            raise DatabaseError("required PostgreSQL migrations are not applied")

    def close(self) -> None:
        pool = self._pool
        if pool is None:
            return
        try:
            pool.close()
        except Exception:
            pass


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def request_hash(body: dict[str, Any]) -> str:
    """Stable hash for idempotency conflict detection."""
    canonical = dict(body)
    # Client timestamps are informational and may be regenerated while a
    # failed request is retried. The idempotency key itself is the lookup key,
    # not part of the semantic payload.
    canonical.pop("created_at", None)
    canonical.pop("idempotency_key", None)
    return hashlib.sha256(json_text(canonical).encode("utf-8")).hexdigest()


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EquipmentRepository:
    """Persistent repository for the Android API projection."""

    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _equipment_row(
        row: dict[str, Any],
        components: list[dict[str, Any]],
        specs: list[dict[str, Any]],
        passport_components: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": row.get("qr_id") or row.get("serial_number") or row["id"],
            "name": row["name"],
            "location": row.get("location"),
            "manufacturer": row.get("manufacturer"),
            "model": row.get("model"),
            "serial_number": row.get("serial_number"),
            "specs": specs,
            "passport_components": passport_components,
            "components": components,
        }

    def get_equipment(self, qr_id: str) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT e.id, e.qr_id, e.serial_number, e.name, e.location,
                           e.manufacturer, e.model
                    FROM promscan.equipment AS e
                    WHERE (upper(COALESCE(e.qr_id, '')) = upper(%s)
                       OR upper(e.id) = upper(%s)
                       OR upper(COALESCE(e.serial_number, '')) = upper(%s)
                       OR EXISTS (
                           SELECT 1 FROM promscan.equipment_aliases AS a
                           WHERE upper(a.alias) = upper(%s) AND a.equipment_id = e.id
                       ))
                    LIMIT 1
                    """,
                    (qr_id, qr_id, qr_id, qr_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                equipment = dict(row)
                cursor.execute(
                    """
                    SELECT COALESCE(public_id, id) AS id, name, description,
                           offset_x, offset_y, offset_z, radius
                    FROM promscan.equipment_nodes
                    WHERE equipment_id = %s
                    ORDER BY sort_order, id
                    """,
                    (equipment["id"],),
                )
                components = []
                for node in cursor.fetchall():
                    node = dict(node)
                    components.append(
                        {
                            "id": node["id"],
                            "name": node["name"],
                            "offset_from_qr": {
                                "x": float(node["offset_x"]),
                                "y": float(node["offset_y"]),
                                "z": float(node["offset_z"]),
                            },
                            "radius": float(node["radius"]),
                            "description": node.get("description"),
                        }
                    )
                cursor.execute(
                    """
                    SELECT label, value, unit
                    FROM promscan.equipment_specs
                    WHERE equipment_id = %s
                    ORDER BY sort_order, id
                    """,
                    (equipment["id"],),
                )
                specs = [dict(row) for row in cursor.fetchall()]
                cursor.execute(
                    """
                    SELECT c.id, c.name, s.label, s.value, s.unit
                    FROM promscan.equipment_components AS c
                    LEFT JOIN promscan.equipment_component_specs AS s
                      ON s.component_id = c.id
                    WHERE c.equipment_id = %s
                    ORDER BY c.sort_order, c.id, s.sort_order, s.id
                    """,
                    (equipment["id"],),
                )
                passport_components_by_id: dict[str, dict[str, Any]] = {}
                for row in cursor.fetchall():
                    item = dict(row)
                    component = passport_components_by_id.setdefault(
                        item["id"], {"id": item["id"], "name": item["name"], "specs": []}
                    )
                    if item["label"] is not None:
                        component["specs"].append(
                            {"label": item["label"], "value": item["value"], "unit": item["unit"]}
                        )
                return self._equipment_row(
                    equipment, components, specs, list(passport_components_by_id.values())
                )

    def list_equipment(self) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(NULLIF(qr_id, ''), serial_number, id) AS id, name
                    FROM promscan.equipment
                    ORDER BY name, id
                    """
                )
                return [dict(row) for row in cursor.fetchall()]

    def list_equipment_documents(self, equipment_id: str) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                internal_id = self._equipment_internal_id(cursor, equipment_id)
                cursor.execute(
                    """
                    SELECT id, file_name, document_type, mime_type, byte_size,
                           encode(sha256, 'hex') AS sha256, imported_at,
                           content IS NOT NULL AS content_available
                    FROM promscan.equipment_documents
                    WHERE equipment_id = %s
                    ORDER BY document_type, file_name, id
                    """,
                    (internal_id,),
                )
                documents = []
                for row in cursor.fetchall():
                    document = dict(row)
                    if document.get("imported_at") is not None:
                        document["imported_at"] = document["imported_at"].isoformat().replace(
                            "+00:00", "Z"
                        )
                    documents.append(document)
                return documents

    def get_equipment_document(self, equipment_id: str, document_id: str) -> dict[str, Any] | None:
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                internal_id = self._equipment_internal_id(cursor, equipment_id)
                cursor.execute(
                    """
                    SELECT id, file_name, mime_type, byte_size,
                           encode(sha256, 'hex') AS sha256, content
                    FROM promscan.equipment_documents
                    WHERE equipment_id = %s AND id::text = %s
                    """,
                    (internal_id, document_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                document = dict(row)
                if document.get("content") is not None:
                    document["content"] = bytes(document["content"])
                return document

    def persist_inspection(
        self,
        equipment: dict[str, Any],
        payload: dict[str, Any],
        image_object: dict[str, Any] | None = None,
    ) -> str:
        inspection_id = new_id()
        defects = payload.get("defects") or []
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                if image_object:
                    cursor.execute(
                        """
                        INSERT INTO promscan_api.object_metadata
                            (id, object_key, bucket, mime_type, byte_size, sha256,
                             etag, equipment_id, inspection_id, purpose)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            image_object["id"], image_object["object_key"], image_object["bucket"],
                            image_object["mime_type"], image_object["byte_size"], image_object["sha256"],
                            image_object.get("etag"), self._equipment_internal_id(cursor, equipment["id"]),
                            inspection_id, "inspection_raw",
                        ),
                    )
                image_object_id = image_object["id"] if image_object else None
                cursor.execute(
                    """
                    INSERT INTO promscan_api.inspections
                        (id, equipment_id, status, source, model, image_object_id,
                         result, completed_at)
                    VALUES (%s, %s, 'completed', 'android', %s, %s, %s::jsonb, now())
                    """,
                    (
                        inspection_id,
                        self._equipment_internal_id(cursor, equipment["id"]),
                        payload.get("model"), image_object_id, json_text(payload),
                    ),
                )
                equipment_internal_id = self._equipment_internal_id(cursor, equipment["id"])
                for index, defect in enumerate(defects):
                    public_id = str(defect.get("id") or f"{inspection_id[:8]}-{index + 1}")
                    defect_id = f"{inspection_id}:{public_id}"
                    node_id = defect.get("node_id")
                    if node_id:
                        cursor.execute(
                            """
                            SELECT 1 FROM promscan.equipment_nodes
                            WHERE equipment_id = %s AND (public_id = %s OR id = %s)
                            """,
                            (equipment_internal_id, node_id, node_id),
                        )
                        if cursor.fetchone() is None:
                            node_id = None
                    cursor.execute(
                        """
                        INSERT INTO promscan_api.defects
                            (id, inspection_id, equipment_id, public_id, node_id, type,
                             title, confidence, severity, polygon, bbox, offset_from_qr,
                             analysis, recommendation, model)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                        """,
                        (
                            defect_id, inspection_id, equipment_internal_id, public_id,
                            node_id, str(defect.get("type") or "unknown"),
                            str(defect.get("title") or "Дефект"),
                            float(defect.get("confidence") or 0),
                            str(defect.get("severity") or "medium"),
                            json_text(defect.get("polygon")) if defect.get("polygon") is not None else None,
                            json_text(defect.get("bbox")) if defect.get("bbox") is not None else None,
                            json_text(defect.get("offset_from_qr"))
                            if defect.get("offset_from_qr") is not None else None,
                            defect.get("analysis"), defect.get("recommendation"), payload.get("model"),
                        ),
                    )
        return inspection_id

    def _equipment_internal_id(self, cursor: Any, qr_id: str) -> str:
        cursor.execute(
            """
            SELECT id FROM promscan.equipment
            WHERE upper(COALESCE(qr_id, '')) = upper(%s)
               OR upper(id) = upper(%s)
               OR upper(COALESCE(serial_number, '')) = upper(%s)
               OR EXISTS (
                   SELECT 1 FROM promscan.equipment_aliases AS a
                   WHERE upper(a.alias) = upper(%s) AND a.equipment_id = promscan.equipment.id
               )
            LIMIT 1
            """,
            (qr_id, qr_id, qr_id, qr_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RepositoryNotFound("equipment does not exist")
        return dict(row)["id"] if not isinstance(row, tuple) else row[0]

    def find_idempotent(self, key: str) -> dict[str, Any] | None:
        if not key:
            return None
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                cursor.execute(
                    "SELECT report_id, resolution_status, created_at, request_hash FROM promscan_api.reports WHERE idempotency_key = %s",
                    (key,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def create_report(
        self,
        body: dict[str, Any],
        report_id: str,
        request_digest: str,
        document_object: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        equipment = str(body["equipment_id"])
        node_id = body.get("node_id")
        public_defect_id = body.get("defect_id")
        resolution_status = str(body["status"])
        internal_equipment_id = None
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                idempotency_key = body.get("idempotency_key")
                if idempotency_key:
                    # Serialize concurrent retries for the same key inside the
                    # transaction; the unique index remains the final guard.
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (idempotency_key,),
                    )
                    cursor.execute(
                        """
                        SELECT report_id, resolution_status, created_at, request_hash
                        FROM promscan_api.reports
                        WHERE idempotency_key = %s
                        """,
                        (idempotency_key,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        existing = dict(existing)
                        if existing.get("request_hash") != request_digest:
                            raise RepositoryConflict(
                                "idempotency key was used for another request"
                            )
                        return {
                            "report_id": existing["report_id"],
                            "status": existing["resolution_status"],
                            "created_at": existing["created_at"].isoformat().replace("+00:00", "Z"),
                        }
                internal_equipment_id = self._equipment_internal_id(cursor, equipment)
                if node_id:
                    cursor.execute(
                        "SELECT 1 FROM promscan.equipment_nodes WHERE equipment_id = %s AND (public_id = %s OR id = %s)",
                        (internal_equipment_id, node_id, node_id),
                    )
                    if cursor.fetchone() is None:
                        raise RepositoryNotFound("node does not belong to equipment")

                defect_id = None
                inspection_id = body.get("inspection_id")
                if inspection_id:
                    cursor.execute(
                        "SELECT 1 FROM promscan_api.inspections WHERE id = %s AND equipment_id = %s",
                        (inspection_id, internal_equipment_id),
                    )
                    if cursor.fetchone() is None:
                        raise RepositoryNotFound("inspection does not exist for equipment")
                if public_defect_id:
                    cursor.execute(
                        """
                        SELECT id, inspection_id, node_id, title
                        FROM promscan_api.defects
                        WHERE equipment_id = %s AND public_id = %s
                          AND (%s IS NULL OR inspection_id = %s)
                        ORDER BY detected_at DESC LIMIT 1
                        """,
                        (internal_equipment_id, public_defect_id, inspection_id, inspection_id),
                    )
                    defect = cursor.fetchone()
                    if defect is None:
                        raise RepositoryNotFound("defect does not exist for equipment")
                    defect = dict(defect)
                    defect_id = defect["id"]
                    inspection_id = inspection_id or defect["inspection_id"]
                    node_id = node_id or defect.get("node_id")
                    body["defect_title"] = body.get("defect_title") or defect.get("title")

                object_id = document_object["id"] if document_object else None
                if document_object:
                    cursor.execute(
                        """
                        INSERT INTO promscan_api.object_metadata
                            (id, object_key, bucket, mime_type, byte_size, sha256,
                             etag, equipment_id, report_id, purpose)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            document_object["id"], document_object["object_key"], document_object["bucket"],
                            document_object["mime_type"], document_object["byte_size"], document_object["sha256"],
                            document_object.get("etag"), internal_equipment_id, report_id, "report_pdf",
                        ),
                    )
                created_at = utc_now()
                cursor.execute(
                    """
                    INSERT INTO promscan_api.reports
                        (id, report_id, equipment_id, inspection_id, node_id, defect_id,
                         defect_title, resolution_status, comment, source, idempotency_key,
                         request_hash, document_object_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING report_id, resolution_status AS status, created_at
                    """,
                    (
                        new_id(), report_id, internal_equipment_id, inspection_id, node_id, defect_id,
                        body.get("defect_title"), resolution_status, body.get("comment"),
                        body.get("source") or "android", body.get("idempotency_key"), request_digest,
                        object_id, created_at, created_at,
                    ),
                )
                result = dict(cursor.fetchone())
                if defect_id:
                    is_false_positive = resolution_status == "false_positive"
                    parts = body.get("required_parts")
                    parts_json = json_text(parts if isinstance(parts, list) else [])
                    cursor.execute(
                        """
                        INSERT INTO promscan_api.defect_resolutions
                            (defect_id, resolution_status, comment, required_parts,
                             is_false_positive, resolved_by, resolved_at, updated_at)
                        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                        ON CONFLICT (defect_id) DO UPDATE SET
                            resolution_status = EXCLUDED.resolution_status,
                            comment = EXCLUDED.comment,
                            required_parts = EXCLUDED.required_parts,
                            is_false_positive = EXCLUDED.is_false_positive,
                            resolved_by = EXCLUDED.resolved_by,
                            resolved_at = EXCLUDED.resolved_at,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (
                            defect_id, resolution_status, body.get("comment"), parts_json,
                            is_false_positive, body.get("actor_id"), created_at, created_at,
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO promscan_api.defect_resolution_history
                            (id, defect_id, resolution_status, comment, required_parts,
                             is_false_positive, resolved_by, created_at)
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                        """,
                        (
                            new_id(), defect_id, resolution_status, body.get("comment"), parts_json,
                            is_false_positive, body.get("actor_id"), created_at,
                        ),
                    )
                return {
                    "report_id": result["report_id"],
                    "status": result["status"],
                    "created_at": result["created_at"].isoformat().replace("+00:00", "Z"),
                }

    def list_reports(self) -> list[dict[str, Any]]:
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT r.report_id, e.qr_id AS equipment_id, r.node_id,
                           d.public_id AS defect_id, r.defect_title,
                           r.resolution_status AS status, r.comment,
                           r.created_at, r.inspection_id
                    FROM promscan_api.reports AS r
                    JOIN promscan.equipment AS e ON e.id = r.equipment_id
                    LEFT JOIN promscan_api.defects AS d ON d.id = r.defect_id
                    ORDER BY r.created_at DESC, r.report_id
                    """
                )
                reports = []
                for row in cursor.fetchall():
                    item = dict(row)
                    if item.get("created_at") is not None:
                        item["created_at"] = item["created_at"].isoformat().replace("+00:00", "Z")
                    reports.append(item)
                return reports

    @staticmethod
    def _document_result(report_id: str, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_id": report_id,
            "object_key": document["object_key"],
            "mime_type": document["mime_type"],
            "byte_size": document["byte_size"],
            "sha256": str(document["sha256"]).strip(),
        }

    def get_report_document(self, report_id: str) -> dict[str, Any] | None:
        """Return document metadata without exposing object bytes."""
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT r.document_object_id, o.object_key, o.mime_type,
                           o.byte_size, o.sha256
                    FROM promscan_api.reports AS r
                    LEFT JOIN promscan_api.object_metadata AS o
                      ON o.id = r.document_object_id
                    WHERE r.report_id = %s
                    """,
                    (report_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RepositoryNotFound("report does not exist")
                row = dict(row)
                if not row.get("document_object_id"):
                    return None
                return self._document_result(report_id, row)

    def attach_report_document(
        self,
        report_id: str,
        document_object: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.connection() as connection:
            with self.database.cursor(connection) as cursor:
                cursor.execute(
                    """
                    SELECT id, equipment_id, document_object_id
                    FROM promscan_api.reports
                    WHERE report_id = %s
                    FOR UPDATE
                    """,
                    (report_id,),
                )
                report = cursor.fetchone()
                if report is None:
                    raise RepositoryNotFound("report does not exist")
                report = dict(report)
                if report.get("document_object_id"):
                    cursor.execute(
                        """
                        SELECT object_key, mime_type, byte_size, sha256
                        FROM promscan_api.object_metadata
                        WHERE id = %s
                        """,
                        (report["document_object_id"],),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        existing = dict(existing)
                        if str(existing["sha256"]).strip() != str(document_object["sha256"]).strip():
                            raise RepositoryConflict("report already has a different document")
                        return self._document_result(report_id, existing)
                cursor.execute(
                    """
                    INSERT INTO promscan_api.object_metadata
                        (id, object_key, bucket, mime_type, byte_size, sha256,
                         etag, equipment_id, report_id, purpose)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (object_key) DO NOTHING
                    """,
                    (
                        document_object["id"], document_object["object_key"], document_object["bucket"],
                        document_object["mime_type"], document_object["byte_size"], document_object["sha256"],
                        document_object.get("etag"), report["equipment_id"], report_id, "report_pdf",
                    ),
                )
                cursor.execute(
                    """
                    SELECT id, object_key, mime_type, byte_size, sha256, report_id
                    FROM promscan_api.object_metadata
                    WHERE object_key = %s
                    """,
                    (document_object["object_key"],),
                )
                stored = cursor.fetchone()
                if stored is None:
                    raise DatabaseError("document metadata was not stored")
                stored = dict(stored)
                if (
                    str(stored["sha256"]).strip() != str(document_object["sha256"]).strip()
                    or stored.get("report_id") != report_id
                ):
                    raise RepositoryConflict("object key is already used by another document")
                cursor.execute(
                    """
                    UPDATE promscan_api.reports
                    SET document_object_id = %s, updated_at = now()
                    WHERE report_id = %s
                    """,
                    (stored["id"], report_id),
                )
                return self._document_result(report_id, stored)
