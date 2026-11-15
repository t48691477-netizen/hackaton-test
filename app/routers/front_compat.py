"""Совместимый с React-фронтом (frontend-test) API. Монтируется на /front, не ломает Android-контракт."""
import json
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.services.detector import defect_detector
from app.services import mailer
from app.services.llm_expert import llm_expert_service
from app.services.storage import storage_service
from app.services.telemetry_emulator import telemetry_service

router = APIRouter(prefix="/front/api", tags=["Front compat"])
REPORTS_FILE = settings.DATA_DIR / "front_reports.json"
_lock = threading.Lock()


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
    telem = telemetry_service.get_current_reading(e.id)
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
    # Добавляем блок телеметрии датчиков в список узлов
    sensor_specs = [
        {"label": ch["name"], "value": str(ch["value"]), "unit": ch["unit"]}
        for ch in telem.get("channels", [])
    ]
    sensor_specs.append({"label": "Диагноз по вибрации", "value": telem.get("diagnosis", "Норма"), "unit": None})
    sensor_specs.append({"label": "Интеграция", "value": "OPC UA / Modbus TCP", "unit": None})

    nodes.insert(0, {
        "id": "node-sensors",
        "name": "📡 Датчики (OPC UA / Modbus)",
        "specs": sensor_specs,
    })

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
        "specs": [
            {"label": "Возраст узлов", "value": e.component_age, "unit": None},
            {"label": "Статус телеметрии", "value": telem.get("diagnosis", "Норма"), "unit": None},
            {"label": "СКЗ вибрации", "value": str(next((c["value"] for c in telem.get("channels", []) if c["id"] == "v_rms"), "1.0")), "unit": "мм/с"},
        ],
        "nodes": nodes,
        "telemetry": telem,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _eq_fallback(equipment_id: str) -> dict:
    d = datetime.now().date().isoformat()
    telem = telemetry_service.get_current_reading(equipment_id)
    sensor_specs = [
        {"label": ch["name"], "value": str(ch["value"]), "unit": ch["unit"]}
        for ch in telem.get("channels", [])
    ]
    sensor_specs.append({"label": "Диагноз по вибрации", "value": telem.get("diagnosis", "Норма"), "unit": None})
    sensor_specs.append({"label": "Интеграция", "value": "OPC UA / Modbus TCP", "unit": None})

    return {
        "id": equipment_id, "name": f"Агрегат {equipment_id}", "inventory_number": equipment_id,
        "category": "Промышленное оборудование", "location": "—", "state": "operational",
        "manufacturer": "—", "model": "—", "commissioned_at": d, "service_life_years": 10,
        "last_maintenance_at": d, "next_maintenance_at": d,
        "specs": [
            {"label": "Статус телеметрии", "value": telem.get("diagnosis", "Норма"), "unit": None},
        ],
        "nodes": [
            {
                "id": "node-sensors",
                "name": "📡 Датчики (OPC UA / Modbus)",
                "specs": sensor_specs,
            }
        ],
        "telemetry": telem,
        "created_at": _now(), "updated_at": _now(),
    }


@router.get("/equipment")
def list_equipment():
    return [_eq(e) for e in storage_service.get_all_equipment()]


@router.get("/equipment/{equipment_id}")
def get_equipment(equipment_id: str):
    e = storage_service.get_equipment_by_id(equipment_id)
    if not e:
        return _eq_fallback(equipment_id)
    return _eq(e)


@router.get("/equipment/{equipment_id}/telemetry")
@router.get("/telemetry/{equipment_id}")
def get_equipment_telemetry(equipment_id: str):
    """Текущий срез телеметрии датчиков по OPC UA / Modbus TCP с сервера ввода/вывода."""
    return telemetry_service.get_current_reading(equipment_id)


@router.get("/telemetry/{equipment_id}/history")
def get_equipment_telemetry_history(equipment_id: str, limit: int = 24):
    """История измерений датчиков из 500-строчного архива для графиков тренда."""
    return telemetry_service.get_history(equipment_id, limit=limit)


@router.post("/telemetry/{equipment_id}/trigger-anomaly")
def trigger_telemetry_anomaly(equipment_id: str):
    """Демо-ручка: принудительно выдаёт срез с аномалией (дисбаланс / расцентровка / износ)."""
    return telemetry_service.get_current_reading(equipment_id, force_anomaly=True)


def _detail(equipment_id: str) -> dict:
    e = storage_service.get_equipment_by_id(equipment_id)
    return _eq(e) if e else _eq_fallback(equipment_id)


_HALF = False
_DEV = "cpu"
try:
    import torch
    if torch.cuda.is_available():
        _HALF, _DEV = True, 0
except Exception:
    pass
IMGSZ = 960
_infer_lock = threading.Lock()
_oil_model = None
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


def _models():
    global _oil_model
    if _unified() is not None:
        return None, None, None
    from app.services.model_loader import model_loader
    c = model_loader.load_corrosion_model()
    w = model_loader.load_welding_model()
    if _oil_model is None:
        p = settings.OIL_LOCAL_PATH
        if p.exists():
            from ultralytics import YOLO
            _oil_model = YOLO(str(p))
    return c, w, _oil_model


def warm_up():
    try:
        import numpy as np
        img = np.zeros((480, 640, 3), np.uint8)
        for m in (_unified(),) + _models():
            if m is not None:
                m.predict(img, imgsz=IMGSZ, half=_HALF, device=_DEV, verbose=False)
    except Exception as exc:
        print(f"[front_compat] warm_up: {exc}")


def _run(model, img, conf, kind, skip, node_id):
    onnx = model is _unified_model
    r = model.predict(img, conf=conf, imgsz=IMGSZ, half=False if onnx else _HALF, device="cpu" if onnx else _DEV, verbose=False, max_det=15)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return []
    bx = r.boxes.xyxyn.cpu().numpy()
    cf = r.boxes.conf.cpu().numpy()
    cl = r.boxes.cls.cpu().numpy().astype(int)
    polys = r.masks.xyn if r.masks is not None else None
    out = []
    for i in range(len(bx)):
        if r.names[int(cl[i])] in skip:
            continue
        kind_i = kind or _kind_of(r.names[int(cl[i])])
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


def _model_names() -> dict:
    if _unified_model is not None:
        return {"all": settings.UNIFIED_LOCAL_PATH.stem}
    return {
        "corrosion": settings.CORROSION_LOCAL_PATH.stem,
        "crack": settings.WELDING_LOCAL_PATH.stem,
        "oil": settings.OIL_LOCAL_PATH.stem,
    }


def _eq_cached(equipment_id: str):
    hit = _eq_cache.get(equipment_id)
    if hit and time.time() - hit[0] < 20:
        return hit[1]
    e = storage_service.get_equipment_by_id(equipment_id)
    _eq_cache[equipment_id] = (time.time(), e)
    return e


@router.post("/inspect")
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
    corr, weld, oil = _models()
    out = []
    uni = _unified()
    with _infer_lock:
        if uni is not None:
            out += _run(uni, img, 0.35, None, set(), node_id)
        if corr is not None:
            out += _run(corr, img, 0.35, "corrosion", {"car"}, node_id)
        if weld is not None:
            out += _run(weld, img, 0.35, "crack", {"Good Weld"}, node_id)
        if oil is not None:
            out += _run(oil, img, 0.30, "oil", set(), node_id)
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
                 "models": _model_names(),
                 "processing_ms": int((time.time() - t0) * 1000), "analyzed_at": _now()},
    }


@router.post("/inspect/detailed")
def inspect_detailed(file: UploadFile = File(...), inspection: str = Form(...), condition_parameters: str = Form("{}")):
    t0 = datetime.now()
    try:
        insp = json.loads(inspection)
    except Exception:
        raise HTTPException(400, "Некорректный inspection.")
    findings = [
        {"title": d.get("label", "Дефект"), "description": f"Уверенность {round(d.get('confidence', 0) * 100)}%, модель {d.get('source_model')}.",
         "severity": d.get("severity", "low"), "recommendation": d.get("recommendation", "")}
        for d in insp.get("defects", [])
    ]
    llm = insp.get("llm", {})
    summary = insp.get("summary", "")
    causes = [llm.get("probable_cause", "")] if llm.get("probable_cause") else []
    steps = llm.get("recommendation_steps", [])
    llm_name = None
    if insp.get("defects"):
        eq = insp.get("equipment") or {}
        payload = json.dumps({
            "equipment_name": eq.get("name") or eq.get("id") or "агрегат",
            "defects_found": [
                {"label": d.get("label"), "source": d.get("source_model"), "confidence": d.get("confidence"), "severity": d.get("severity")}
                for d in insp["defects"]
            ],
            "defects_count": len(insp["defects"]),
        }, ensure_ascii=False)
        res = llm_expert_service._ollama_chat(f"ВХОДНЫЕ ДАННЫЕ:\n{payload}")
        if res:
            cause = res.get("probable_cause")
            recs = res.get("recommendations") or []
            if isinstance(recs, str):
                recs = [recs]
            if cause or recs:
                causes = [str(cause)] if cause else causes
                steps = [str(r) for r in recs] or steps
                llm_name = settings.OLLAMA_MODEL
                crit = str(res.get("criticality", "")).lower()
                if crit in _SEV_RANK:
                    insp.setdefault("llm", {})["criticality"] = crit
    return {
        "analysis_id": f"an-{uuid.uuid4().hex[:10]}", "inspection_id": insp.get("inspection_id", ""),
        "summary": summary, "findings": findings,
        "probable_causes": causes,
        "recommendation_steps": steps,
        "criticality": insp.get("llm", {}).get("criticality"),
        "models": list(_model_names().values()) + ([llm_name] if llm_name else []),
        "processing_ms": int((datetime.now() - t0).total_seconds() * 1000), "analyzed_at": _now(),
    }


def _load() -> list:
    if REPORTS_FILE.exists():
        return json.loads(REPORTS_FILE.read_text(encoding="utf-8"))
    return []


def _save(items: list) -> None:
    REPORTS_FILE.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


@router.get("/reports")
def list_reports(status: Optional[str] = None):
    with _lock:
        items = _load()
    return [r for r in items if not status or r["status"] == status]


@router.get("/reports/{report_id}")
def get_report(report_id: str):
    with _lock:
        for r in _load():
            if r["id"] == report_id:
                return r
    raise HTTPException(404, "Отчёт не найден.")


@router.post("/reports")
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
    now = _now()
    rep = {
        "id": f"report-{uuid.uuid4().hex[:10]}", "equipment_id": equipment_id, "inspection_id": inspection_id,
        "status": status, "comment": comment, "photo_url": photo_url, "result": json.loads(payload),
        "assignee": {"id": assignee_id, "full_name": assignee_id} if assignee_id else None,
        "started_at": None if status == "open" else now, "completed_at": now if status == "closed" else None,
        "repair_comment": None, "created_at": now, "updated_at": now,
    }
    try:
        storage_service.increment_inspection_count(equipment_id)
    except Exception:
        pass
    with _lock:
        items = _load()
        items.insert(0, rep)
        _save(items)
    return rep


class StatusIn(BaseModel):
    status: str
    comment: Optional[str] = None


@router.patch("/reports/{report_id}/status")
def patch_status(report_id: str, body: StatusIn):
    with _lock:
        items = _load()
        rep = next((r for r in items if r["id"] == report_id), None)
        if rep is None:
            raise HTTPException(404, "Отчёт не найден.")
        if body.status == rep["status"]:
            return rep
        if body.status == "in_progress" and rep["status"] != "open":
            raise HTTPException(409, "Начать можно только назначенную задачу.")
        if body.status == "closed" and rep["status"] != "in_progress":
            raise HTTPException(409, "Завершить можно только задачу в работе.")
        if body.status not in ("in_progress", "closed"):
            raise HTTPException(422, "Неверный статус.")
        if not rep["assignee"]:
            raise HTTPException(409, "Сначала назначьте задачу сотруднику.")
        now = _now()
        rep["status"], rep["updated_at"] = body.status, now
        rep["started_at"] = rep["started_at"] or now
        if body.status == "closed":
            rep["completed_at"] = now
        if body.comment is not None:
            rep["repair_comment"] = body.comment
        _save(items)
        return rep

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
