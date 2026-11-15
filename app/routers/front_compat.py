"""Совместимый с React-фронтом (frontend-test) API. Монтируется на /front, не ломает Android-контракт."""
import json
import os
import shlex
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.services import mailer
from app.services.db import DatabaseError, DatabaseUnavailable
from app.routers._deps import storage_dep

router = APIRouter(prefix="/front/api", tags=["Front compat"])
_lock = threading.Lock()


def _database_errors_as_503(endpoint):
    @wraps(endpoint)
    def wrapped(*args, **kwargs):
        try:
            return endpoint(*args, **kwargs)
        except DatabaseError as exc:
            raise HTTPException(503, "Хранилище PostgreSQL временно недоступно.") from exc

    return wrapped


def _dsn_identity(dsn: str) -> tuple[str, str, str]:
    if "://" in dsn:
        parsed = urlsplit(dsn)
        database = unquote(parsed.path.lstrip("/")) or unquote(parsed.username or "")
        return (parsed.hostname or "localhost", str(parsed.port or 5432), database)
    params = {}
    try:
        for token in shlex.split(dsn):
            key, value = token.split("=", 1)
            params[key.lower()] = value
    except (ValueError, TypeError):
        return ("dsn", "", dsn.strip())
    database = params.get("dbname") or params.get("database") or params.get("user", "")
    return (
        params.get("host", "localhost"),
        params.get("port", "5432"),
        database,
    )


def _require_separate_database(env_name: str, pool=None) -> None:
    dsn = os.getenv(env_name, "").strip()
    if not dsn:
        raise DatabaseUnavailable(f"{env_name} должен указывать на отдельную PostgreSQL БД")

    catalog_dsn = (
        os.getenv("DATABASE_URL", "").strip()
        or os.getenv("DATABASE_CATALOG_URL", "").strip()
    )
    configured = {
        name: os.getenv(name, "").strip()
        for name in ("DATABASE_TASKS_URL", "DATABASE_EMPLOYEES_URL")
        if name != env_name and os.getenv(name, "").strip()
    }
    credentials_dsn = os.getenv("DATABASE_CREDENTIALS_URL", "").strip()
    if credentials_dsn:
        configured["DATABASE_CREDENTIALS_URL"] = credentials_dsn
    if catalog_dsn:
        configured["DATABASE_URL"] = catalog_dsn
    target = _dsn_identity(dsn)
    if any(target == _dsn_identity(other) for other in configured.values()):
        raise DatabaseUnavailable(f"{env_name} совпадает с физической PostgreSQL БД другого сервиса")
    if pool is not None and _dsn_identity(pool.dsn) != target:
        raise DatabaseUnavailable(f"Пул {env_name} создан с другим PostgreSQL DSN")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sev(conf: float) -> str:
    return "high" if conf >= 0.7 else "medium" if conf >= 0.45 else "low"


def _state(status: str) -> str:
    s = (status or "").lower()
    if any(k in s for k in ("fault", "неиспр", "авар")):
        return "fault"
    if any(k in s for k in ("maint", "обслуж", "ремонт")):
        return "maintenance"
    return "operational"


def _add_days(date_str: str, days: int) -> str:
    try:
        return (datetime.fromisoformat(date_str[:10]) + timedelta(days=days)).date().isoformat()
    except Exception:
        return date_str


def _eq(e) -> dict:
    nodes = [
        {
            "id": c.id,
            "name": c.name,
            "specs": [
                {"label": "Тип", "value": c.type, "unit": None},
                {"label": "Возраст", "value": str(c.age_months), "unit": "мес."},
            ],
        }
        for c in e.components
    ]
    return {
        "id": e.id,
        "name": e.name,
        "inventory_number": e.serial_number,
        "category": "Промышленное оборудование",
        "location": e.location,
        "state": _state(e.status),
        "manufacturer": "—",
        "model": e.name,
        "commissioned_at": e.installation_date,
        "service_life_years": 10,
        "last_maintenance_at": e.last_maintenance_date,
        "next_maintenance_at": _add_days(e.last_maintenance_date, 180),
        "specs": [{"label": "Возраст узлов", "value": e.component_age, "unit": None}],
        "nodes": nodes,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _eq_fallback(equipment_id: str) -> dict:
    d = datetime.now().date().isoformat()
    return {
        "id": equipment_id, "name": f"Агрегат {equipment_id}", "inventory_number": equipment_id,
        "category": "Промышленное оборудование", "location": "—", "state": "operational",
        "manufacturer": "—", "model": "—", "commissioned_at": d, "service_life_years": 10,
        "last_maintenance_at": d, "next_maintenance_at": d, "specs": [], "nodes": [],
        "created_at": _now(), "updated_at": _now(),
    }


@router.get("/equipment")
@_database_errors_as_503
def list_equipment():
    return [_eq(e) for e in storage_dep().get_all_equipment()]


@router.get("/equipment/{equipment_id}")
@_database_errors_as_503
def get_equipment(equipment_id: str):
    e = storage_dep().get_equipment_by_id(equipment_id)
    if not e:
        raise HTTPException(404, "Оборудование не найдено.")
    return _eq(e)


def _detail(equipment_id: str) -> dict:
    e = storage_dep().get_equipment_by_id(equipment_id)
    return _eq(e) if e else _eq_fallback(equipment_id)


IMGSZ = 640
_infer_lock = threading.Lock()
_unified_model = None
_unified_tried = False
_eq_cache: dict = {}
_KIND = {
    "corrosion": ("Коррозия", "Зачистить поражённую поверхность, нанести антикоррозионное покрытие.", "Воздействие влаги и разрушение защитного покрытия"),
    "crack": ("Дефект сварного шва", "Провести контроль шва (ВИК/УЗК), при подтверждении переварить.", "Нарушение технологии сварки или перегрузка шва"),
    "oil": ("Утечка масла", "Проверить уплотнения и фланцы, устранить течь, проверить уровень масла.", "Износ уплотнений или ослабление соединений"),
}
_SEV_RANK = {"low": 0, "medium": 1, "high": 2}


def _kind_of(name: str):
    n = name.strip().lower()
    if n == "good weld":
        return None
    if "rust" in n or "corros" in n:
        return "corrosion"
    if "oil" in n:
        return "oil"
    return "crack"


def _unified():
    global _unified_model, _unified_tried
    if not _unified_tried:
        _unified_tried = True
        p = settings.UNIFIED_LOCAL_PATH
        if p.exists():
            try:
                from ultralytics import YOLO
                _unified_model = YOLO(str(p), task="detect")
            except Exception as exc:
                print(f"[front_compat] unified model: {exc}")
    return _unified_model


def warm_up():
    try:
        import numpy as np
        img = np.zeros((480, 640, 3), np.uint8)
        model = _unified()
        if model is not None:
            model.predict(img, imgsz=IMGSZ, device="cpu", verbose=False)
    except Exception as exc:
        print(f"[front_compat] warm_up: {exc}")


def _run(model, img, conf, node_id):
    r = model.predict(img, conf=conf, imgsz=IMGSZ, device="cpu", verbose=False, max_det=15)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return []
    bx = r.boxes.xyxyn.cpu().numpy()
    cf = r.boxes.conf.cpu().numpy()
    cl = r.boxes.cls.cpu().numpy().astype(int)
    polys = r.masks.xyn if r.masks is not None else None
    out = []
    for i in range(len(bx)):
        kind_i = _kind_of(r.names[int(cl[i])])
        if kind_i is None:
            continue
        title, rec, _ = _KIND[kind_i]
        poly = None
        if polys is not None and i < len(polys) and len(polys[i]) >= 3:
            step = max(1, len(polys[i]) // 40)
            poly = [[round(float(x), 4), round(float(y), 4)] for x, y in polys[i][::step]]
        c = float(cf[i])
        out.append({
            "id": f"{kind_i}-{i + 1}", "label": title, "confidence": round(c, 3), "severity": _sev(c),
            "bbox": [round(max(0.0, min(1.0, float(v))), 4) for v in bx[i]], "polygon": poly,
            "node_id": node_id, "source_model": kind_i, "recommendation": rec,
        })
    return out


def _eq_cached(equipment_id: str):
    hit = _eq_cache.get(equipment_id)
    if hit and time.time() - hit[0] < 20:
        return hit[1]
    e = storage_dep().get_equipment_by_id(equipment_id)
    _eq_cache[equipment_id] = (time.time(), e)
    return e


@router.post("/inspect")
@_database_errors_as_503
def inspect(file: UploadFile = File(...), equipment_id: str = Form(...)):
    import cv2
    import numpy as np
    t0 = time.time()
    img = cv2.imdecode(np.frombuffer(file.file.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "Не удалось прочитать изображение.")
    h, w = img.shape[:2]
    if max(h, w) > IMGSZ:
        k = IMGSZ / max(h, w)
        img = cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
    eq = _eq_cached(equipment_id)
    node_id = eq.components[0].id if eq and eq.components else None
    out = []
    uni = _unified()
    with _infer_lock:
        if uni is not None:
            out += _run(uni, img, 0.35, node_id)
    mx = lambda k: max([d["confidence"] for d in out if d["source_model"] == k], default=0.0)
    crit = max((d["severity"] for d in out), key=lambda v: _SEV_RANK[v], default="low")
    kinds = []
    for d in out:
        if d["source_model"] not in kinds:
            kinds.append(d["source_model"])
    cause = "; ".join(_KIND[k][2] for k in kinds) if kinds else "Дефектов не обнаружено."
    steps = [_KIND[k][1] for k in kinds] or ["Продолжить плановый осмотр."]
    return {
        "inspection_id": f"insp-{uuid.uuid4().hex[:10]}",
        "equipment": _eq(eq) if eq else _eq_fallback(equipment_id),
        "defects": out,
        "condition_parameters": {"oil_leak_probability": mx("oil"), "rust_probability": mx("corrosion"), "poor_weld_probability": mx("crack")},
        "llm": {"criticality": crit, "probable_cause": cause, "recommendation_steps": steps},
        "summary": f"Найдено дефектов: {len(out)}. {cause}" if out else "Дефектов не обнаружено.",
        "meta": {"vision_mode": "real", "llm_mode": "mock",
                 "models": {"all": settings.UNIFIED_LOCAL_PATH.stem},
                 "processing_ms": int((time.time() - t0) * 1000), "analyzed_at": _now()},
    }


def _load() -> list:
    # Хранилище задач переведено на PostgreSQL (promscan.reports).
    rows = _tasks_repo.list_reports()
    return [_task_to_front(r) for r in rows]


def _save(items: list) -> None:
    raise RuntimeError("Сохранение в файл front_reports.json удалено: задачи хранятся в PostgreSQL")


def _task_to_front(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "equipment_id": row["equipment_id"],
        "inspection_id": row["inspection_id"],
        "status": row["status"],
        "comment": row.get("comment") or "",
        "photo_url": row.get("photo_url"),
        "result": row.get("result") or {},
        "assignee": (
            {"id": str(row["assignee_id"]), "full_name": row.get("assignee_full_name") or ""}
            if row.get("assignee_id")
            else None
        ),
        "started_at": _pg_iso(row.get("started_at")),
        "completed_at": _pg_iso(row.get("completed_at")),
        "repair_comment": row.get("repair_comment"),
        "created_at": _pg_iso(row.get("created_at")),
        "updated_at": _pg_iso(row.get("updated_at")),
    }


def _pg_iso(value):
    if value is None:
        return None
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    if text.endswith("+00:00"):
        text = text[:-6] + "Z"
    return text


class _FrontTasksRepo:
    """Тонкая обёртка над promscan.reports для маршрутов /front/api/reports."""

    _FIELDS = """
        id, equipment_id, inspection_id, status, comment, photo_url, result,
        assignee_id, assignee_full_name, started_at, completed_at,
        repair_comment, created_at, updated_at
    """

    def __init__(self):
        from app.services.db import pools

        self._pools = pools

    def _cursor(self):
        _require_separate_database("DATABASE_TASKS_URL")
        pool = self._pools.get("tasks")
        _require_separate_database("DATABASE_TASKS_URL", pool)
        return pool.cursor()

    @staticmethod
    def _employee_full_name(employee_id: str) -> Optional[str]:
        _require_separate_database("DATABASE_EMPLOYEES_URL")
        service = storage_dep()
        _require_separate_database("DATABASE_EMPLOYEES_URL", service.employees_pool)
        return service.get_employee_full_name(employee_id)

    def list_reports(self, status: Optional[str] = None) -> list:
        with self._cursor() as cur:
            if status:
                cur.execute(
                    f"SELECT {self._FIELDS} FROM promscan.reports WHERE status = %s ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cur.execute(
                    f"SELECT {self._FIELDS} FROM promscan.reports ORDER BY created_at DESC"
                )
            return [dict(r) for r in cur.fetchall()]

    def get(self, report_id: str) -> Optional[dict]:
        try:
            uuid.UUID(report_id)
        except (ValueError, TypeError, AttributeError):
            return None
        with self._cursor() as cur:
            cur.execute(
                f"SELECT {self._FIELDS} FROM promscan.reports WHERE id = %s",
                (report_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None

    def create(
        self,
        equipment_id: str,
        inspection_id: str,
        status: str,
        comment: str,
        result: dict,
        photo_url: Optional[str],
        assignee_id: Optional[str],
    ) -> dict:
        assignee_full_name = None
        if assignee_id:
            assignee_full_name = self._employee_full_name(assignee_id) or assignee_id
        with self._cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO promscan.reports (
                    equipment_id, inspection_id, status, comment, photo_url,
                    result, assignee_id, assignee_full_name
                ) VALUES (%s, %s, 'open', %s, %s, %s, %s, %s)
                RETURNING id, equipment_id, inspection_id, status, comment,
                          photo_url, result, assignee_id, assignee_full_name,
                          started_at, completed_at, repair_comment,
                          created_at, updated_at
                """,
                (
                    equipment_id,
                    inspection_id,
                    comment,
                    photo_url,
                    json.dumps(result),
                    assignee_id,
                    assignee_full_name,
                ),
            )
            row = dict(cur.fetchone())
            if status in ("in_progress", "closed"):
                chain = ["in_progress"] + (["closed"] if status == "closed" else [])
                for nxt in chain:
                    cur.execute(
                        """
                        UPDATE promscan.reports SET status = %s WHERE id = %s
                        RETURNING id, equipment_id, inspection_id, status, comment,
                                  photo_url, result, assignee_id, assignee_full_name,
                                  started_at, completed_at, repair_comment,
                                  created_at, updated_at
                        """,
                        (nxt, row["id"]),
                    )
                    row = dict(cur.fetchone())
        return row

    def patch_status(self, report_id: str, new_status: str, comment: Optional[str]) -> tuple[Optional[dict], Optional[str]]:
        """Возвращает (row, error): error — not_found|invalid|invalid_status|unassigned."""
        try:
            uuid.UUID(report_id)
        except (ValueError, TypeError, AttributeError):
            return None, "not_found"
        try:
            with self._cursor(commit=True) as cur:
                cur.execute(
                    f"SELECT {self._FIELDS} FROM promscan.reports WHERE id = %s",
                    (report_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None, "not_found"
                row = dict(row)
                if new_status == row["status"]:
                    return row, None
                if new_status not in ("in_progress", "closed"):
                    return None, "invalid_status"
                if new_status == "in_progress" and row["status"] != "open":
                    return None, "invalid"
                if new_status == "closed" and row["status"] != "in_progress":
                    return None, "invalid"
                if not row.get("assignee_id"):
                    return None, "unassigned"
                cur.execute(
                    """
                    UPDATE promscan.reports
                    SET status = %s,
                        repair_comment = COALESCE(%s, repair_comment)
                    WHERE id = %s
                    RETURNING id, equipment_id, inspection_id, status, comment,
                              photo_url, result, assignee_id, assignee_full_name,
                              started_at, completed_at, repair_comment,
                              created_at, updated_at
                    """,
                    (new_status, comment, report_id),
                )
                updated = cur.fetchone()
            if updated is None:
                return None, "invalid"
            return dict(updated), None
        except DatabaseError as exc:
            if getattr(exc.__cause__, "sqlstate", None) == "23514":
                return None, "invalid"
            raise


_tasks_repo = _FrontTasksRepo()


@router.get("/reports")
@_database_errors_as_503
def list_reports(status: Optional[str] = None):
    if status is not None and status not in ("open", "in_progress", "closed", "rejected"):
        raise HTTPException(422, "Неверный статус.")
    return [_task_to_front(r) for r in _tasks_repo.list_reports(status)]


@router.get("/reports/{report_id}")
@_database_errors_as_503
def get_report(report_id: str):
    row = _tasks_repo.get(report_id)
    if row is None:
        raise HTTPException(404, "Отчёт не найден.")
    return _task_to_front(row)


@router.post("/reports")
@_database_errors_as_503
def create_report(
    request: Request,
    equipment_id: str = Form(...), inspection_id: str = Form(...), status: str = Form("open"),
    comment: str = Form(""), payload: str = Form(...), assignee_id: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
):
    if status not in ("open", "in_progress", "closed"):
        raise HTTPException(422, "Неверный статус.")
    photo_url = None
    if photo is not None:
        name = f"report_{uuid.uuid4().hex[:10]}.jpg"
        with open(settings.UPLOAD_DIR / name, "wb") as fh:
            shutil.copyfileobj(photo.file, fh)
        photo_url = f"/static/uploads/{name}"
    try:
        result_payload = json.loads(payload)
    except Exception:
        raise HTTPException(422, "Некорректный payload.")
    if not isinstance(result_payload, dict):
        raise HTTPException(422, "payload должен быть JSON-объектом.")
    if not equipment_id.strip() or not inspection_id.strip():
        raise HTTPException(422, "equipment_id и inspection_id обязательны.")
    assignee_id = assignee_id or None
    if status != "open" and not assignee_id:
        raise HTTPException(409, "Сначала назначьте задачу сотруднику.")
    if assignee_id:
        try:
            uuid.UUID(assignee_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, "assignee_id должен быть UUID.")
    row = _tasks_repo.create(
        equipment_id=equipment_id,
        inspection_id=inspection_id,
        status=status,
        comment=comment,
        result=result_payload,
        photo_url=photo_url,
        assignee_id=assignee_id,
    )
    try:
        storage_dep().increment_inspection_count(equipment_id)
    except Exception:
        pass
    return _task_to_front(row)


class StatusIn(BaseModel):
    status: str
    comment: Optional[str] = None


@router.patch("/reports/{report_id}/status")
@_database_errors_as_503
def patch_status(report_id: str, body: StatusIn):
    row, error = _tasks_repo.patch_status(report_id, body.status, body.comment)
    if error == "not_found":
        raise HTTPException(404, "Отчёт не найден.")
    if error == "invalid":
        raise HTTPException(409, "Недопустимый переход статуса.")
    if error == "invalid_status":
        raise HTTPException(422, "Неверный статус.")
    if error == "unassigned":
        raise HTTPException(409, "Сначала назначьте задачу сотруднику.")
    repeated_rejected = (
        body.status == "rejected"
        and row is not None
        and row.get("status") == "rejected"
    )
    if body.status not in ("in_progress", "closed", "open") and not repeated_rejected:
        # body.status open не меняет состояние, но контракт PATCH допускает
        # только in_progress/closed; open возвращаем как текущее состояние.
        # Уже отклонённый report можно безопасно повторно подтвердить.
        raise HTTPException(422, "Неверный статус.")
    return _task_to_front(row)

_EMAIL_RE = r"^[^@\s<>,;\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,}$"


class AccessKeyMail(BaseModel):
    to: str = Field(pattern=_EMAIL_RE, max_length=254)
    full_name: str = Field(min_length=1, max_length=120, pattern=r"^[^\r\n]+$")
    role: str = Field(min_length=1, max_length=60, pattern=r"^[^\r\n]+$")
    access_key: str = Field(min_length=6, max_length=32, pattern=r"^[A-Za-z0-9-]+$")


@router.post("/mail/access-key")
def send_access_key_mail(body: AccessKeyMail):
    try:
        message_id = mailer.send_access_key(body.to, body.full_name, body.role, body.access_key)
    except mailer.MailNotConfigured as exc:
        raise HTTPException(503, str(exc))
    except mailer.MailRateLimited as exc:
        raise HTTPException(429, str(exc))
    except mailer.MailDeliveryError as exc:
        raise HTTPException(502, str(exc))
    return {"status": "sent", "message_id": message_id}
