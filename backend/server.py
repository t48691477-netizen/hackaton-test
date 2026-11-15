#!/usr/bin/env python3
"""
AR-Инспектор · бэкенд «Кибер 102».

Работает в двух режимах:

1. MOCK (по умолчанию) — отдаёт заранее подготовленные дефекты. Ни сети,
   ни ключей. Это страховка на сцене.
2. LIVE — если заданы переменные окружения, кадр уходит в настоящую
   vision-модель, а разбор пишет LLM. Приложение при этом не меняется:
   контракт /api/inspect один и тот же.

Запуск:
    python backend/server.py              # mock, порт 8080
    python backend/server.py 9000         # другой порт

Live-режим (любой OpenAI-совместимый провайдер):
    $env:LLM_BASE_URL="https://api.<провайдер>.com/v1"
    $env:LLM_API_KEY="<ключ>"
    $env:LLM_MODEL="<модель с поддержкой изображений>"
    python backend/server.py

Эндпоинты:
    GET  /api/health          — статус + режим (mock/live) + имя модели
    GET  /api/equipment/{id}  — паспорт оборудования и компоненты
    POST /api/inspect         — кадр → дефекты с полигонами
    POST /api/chat            — ассистент «Моттэл»
    POST /api/reports         — сохранить акт
    GET  /api/reports         — список актов
    GET  /qr/{id}             — QR-страница для демонстрации
    GET  /                    — список оборудования

Ключи НИКОГДА не попадают в APK: приложение говорит только с этим сервером.
"""

import base64
import binascii
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

try:
    from app.services.telemetry_emulator import telemetry_service
except Exception:
    telemetry_service = None

try:
    from db import (
        Database,
        DatabaseError,
        EquipmentRepository,
        RepositoryConflict,
        RepositoryNotFound,
        request_hash,
    )
    from migrate import apply_migrations
    from object_storage import ObjectStorageError, S3ObjectStorage
except ImportError:  # importing as backend.server from a package in tests
    from backend.db import (  # type: ignore
        Database,
        DatabaseError,
        EquipmentRepository,
        RepositoryConflict,
        RepositoryNotFound,
        request_hash,
    )
    from backend.migrate import apply_migrations  # type: ignore
    from backend.object_storage import ObjectStorageError, S3ObjectStorage  # type: ignore

# Консоль Windows часто в cp1251: без этого печать падала на любом символе.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

STATE_LOCK = threading.Lock()
REPORTS = []

APP_PROFILE = (os.getenv("APP_PROFILE") or os.getenv("BACKEND_PROFILE") or "mock").strip().lower()
if APP_PROFILE in ("prod", "production"):
    APP_PROFILE = "production"
elif APP_PROFILE in ("mock", "demo"):
    APP_PROFILE = "mock"
else:
    raise ValueError("APP_PROFILE must be 'mock' or 'production'")
PRODUCTION_MODE = APP_PROFILE == "production"
DB_AUTO_MIGRATE = (os.getenv("DB_AUTO_MIGRATE") or "false").strip().lower() in (
    "1", "true", "yes", "on"
)
DATABASE = None
REPOSITORY = None
OBJECT_STORAGE = S3ObjectStorage()
PERSISTENCE_ERROR = None

LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-4o-mini"
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT") or 45)
LIVE_MODE = bool(LLM_BASE_URL and LLM_API_KEY)

REPORT_STATUSES = {"fixed_on_site", "parts_required", "false_positive"}
MAX_IMAGE_BYTES = max(1, int(os.getenv("MAX_IMAGE_BYTES") or str(10 * 1024 * 1024)))
MAX_DOCUMENT_BYTES = max(1, int(os.getenv("MAX_DOCUMENT_BYTES") or str(25 * 1024 * 1024)))
MAX_REQUEST_BYTES = MAX_DOCUMENT_BYTES * 4 // 3 + 2 * 1024 * 1024
REPORT_ID_RE = re.compile(r"ACT-\d{6}-[A-Z0-9]{4}")


def configure_persistence():
    """Initialize production persistence without touching mock startup."""
    global DATABASE, REPOSITORY, PERSISTENCE_ERROR
    if not PRODUCTION_MODE:
        return True
    try:
        DATABASE = Database()
        if DB_AUTO_MIGRATE:
            apply_migrations(DATABASE)
        REPOSITORY = EquipmentRepository(DATABASE)
        DATABASE.check_schema()
        PERSISTENCE_ERROR = None
        return True
    except DatabaseError as error:
        if DATABASE is not None:
            DATABASE.close()
        DATABASE = None
        REPOSITORY = None
        PERSISTENCE_ERROR = str(error)
        return False


def persistence_error_payload():
    # Never echo DSNs, passwords, object-storage keys or driver tracebacks.
    return {"error": "persistent storage unavailable", "profile": APP_PROFILE}


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def model_name():
    return LLM_MODEL if LIVE_MODE else "mock-vision"


EQUIPMENT = {
    "PUMP-402": {
        "id": "PUMP-402",
        "name": "Насосный агрегат ЦНС 38-220",
        "location": "Цех №4 · Насосная станция, поз. 12",
        "components": [
            {"id": "C1", "name": "Корпус насоса", "offset_from_qr": {"x": 0.0, "y": 0.10, "z": 0.0},
             "radius": 0.30, "description": "Основной корпус, чугун СЧ20"},
            {"id": "C2", "name": "Патрубок нагнетания", "offset_from_qr": {"x": 0.32, "y": 0.36, "z": 0.06},
             "radius": 0.22, "description": "DN100, рабочее давление 1.6 МПа"},
            {"id": "C3", "name": "Фланец №3", "offset_from_qr": {"x": -0.28, "y": 0.44, "z": -0.04},
             "radius": 0.20, "description": "Фланцевое соединение, 8 болтов М20"},
            {"id": "C4", "name": "Подшипниковый узел", "offset_from_qr": {"x": 0.14, "y": -0.02, "z": 0.26},
             "radius": 0.24, "description": "Подшипник 3620, смазка Литол-24"},
            {"id": "C5", "name": "Электродвигатель", "offset_from_qr": {"x": -0.40, "y": 0.18, "z": 0.44},
             "radius": 0.32, "description": "АИР160S4, 15 кВт"},
            {"id": "C6", "name": "Муфта", "offset_from_qr": {"x": 0.06, "y": 0.24, "z": 0.40},
             "radius": 0.20, "description": "Упругая втулочно-пальцевая муфта"},
        ],
    },
    "PUMP-118": {
        "id": "PUMP-118",
        "name": "Насос центробежный К-80",
        "location": "Цех №2 · Линия подачи реагента",
        "components": [
            {"id": "C1", "name": "Корпус", "offset_from_qr": {"x": 0.0, "y": 0.10, "z": 0.0}, "radius": 0.28},
            {"id": "C2", "name": "Патрубок", "offset_from_qr": {"x": 0.30, "y": 0.30, "z": 0.0}, "radius": 0.20},
            {"id": "C3", "name": "Опорная рама", "offset_from_qr": {"x": -0.25, "y": -0.05, "z": 0.20}, "radius": 0.24},
        ],
    },
    "VALVE-77": {
        "id": "VALVE-77",
        "name": "Задвижка клиновая DN200",
        "location": "Цех №4 · Узел №7",
        "components": [
            {"id": "C1", "name": "Корпус задвижки", "offset_from_qr": {"x": 0.0, "y": 0.05, "z": 0.0}, "radius": 0.26},
            {"id": "C2", "name": "Шпиндель", "offset_from_qr": {"x": 0.0, "y": 0.35, "z": 0.0}, "radius": 0.18},
            {"id": "C3", "name": "Фланцы", "offset_from_qr": {"x": 0.28, "y": 0.10, "z": 0.0}, "radius": 0.20},
        ],
    },
}

# Сценарий дефектов для mock-режима: одинаковый, чтобы питч был предсказуемым.
DEFECTS = {
    "PUMP-402": {
        "status": "high",
        "model": "mock-vision",
        "analysis": (
            "Зафиксировано 3 дефекта, два из них высокого риска. Критический узел — фланец №3: "
            "коррозия прогрессирует по кромке, есть риск разгерметизации соединения под давлением. "
            "Корпус насоса требует УЗК-контроля. Рекомендуется остановить агрегат и оформить акт ТО "
            "с заказом запчастей."
        ),
        "defects": [
            {
                "id": "D-402-1", "node_id": "C3", "type": "rust",
                "title": "Коррозия фланцевого соединения",
                "confidence": 0.94, "severity": "high",
                "polygon": [
                    {"x": 0.54, "y": 0.345}, {"x": 0.66, "y": 0.300}, {"x": 0.77, "y": 0.365},
                    {"x": 0.79, "y": 0.480}, {"x": 0.69, "y": 0.550}, {"x": 0.56, "y": 0.505},
                ],
                "analysis": (
                    "На поверхности фланца №3 обнаружен очаг коррозии с локальной потерей сечения "
                    "до 12%. Наиболее вероятная причина — разрушение прокладки и постоянный контакт "
                    "с влажной средой. Риск: потеря герметичности и разгерметизация соединения."
                ),
                "recommendation": (
                    "Зачистить поверхность до металла, заменить прокладку, протянуть крепёж "
                    "моментом 120 Н·м. Повторный осмотр через 72 часа."
                ),
            },
            {
                "id": "D-402-2", "node_id": "C1", "type": "crack",
                "title": "Трещина на корпусе насоса",
                "confidence": 0.87, "severity": "high",
                "bbox": [0.245, 0.555, 0.415, 0.700],
                "polygon": [
                    {"x": 0.245, "y": 0.555}, {"x": 0.415, "y": 0.555},
                    {"x": 0.415, "y": 0.700}, {"x": 0.245, "y": 0.700},
                ],
                "analysis": (
                    "Линейный дефект длиной ~38 мм с ветвлением, характерным для усталостной "
                    "трещины. Расположен в зоне концентрации напряжений у опорного пояса. "
                    "Требует немедленной разгрузки узла."
                ),
                "recommendation": (
                    "Остановить агрегат, провести УЗК-контроль, подготовить замену корпуса. "
                    "Эксплуатация до устранения не рекомендуется."
                ),
            },
            {
                "id": "D-402-3", "node_id": "C6", "type": "rust",
                "title": "Поверхностная коррозия муфты",
                "confidence": 0.72, "severity": "medium",
                "polygon": [
                    {"x": 0.435, "y": 0.605}, {"x": 0.520, "y": 0.585},
                    {"x": 0.545, "y": 0.655}, {"x": 0.455, "y": 0.680},
                ],
                "analysis": (
                    "Поверхностная коррозия без признаков потери сечения. На эксплуатацию влияет "
                    "слабо, но требует защиты покрытием."
                ),
                "recommendation": "Обработать преобразователем ржавчины и покрыть защитным составом.",
            },
        ],
    },
    "PUMP-118": {
        "status": "medium",
        "model": "mock-vision",
        "analysis": (
            "Обнаружен один дефект средней критичности. Оборудование сохраняет работоспособность, "
            "требуется плановое ТО."
        ),
        "defects": [
            {
                "id": "D-118-1", "node_id": "C2", "type": "wear",
                "title": "Износ уплотнения патрубка",
                "confidence": 0.78, "severity": "medium",
                "polygon": [
                    {"x": 0.52, "y": 0.38}, {"x": 0.70, "y": 0.34},
                    {"x": 0.76, "y": 0.46}, {"x": 0.60, "y": 0.52},
                ],
                "analysis": (
                    "Кромка уплотнения имеет следы абразивного износа. Риск протечки при повышении "
                    "давления выше 1.2 МПа."
                ),
                "recommendation": "Заменить уплотнение в плановом порядке.",
            },
        ],
    },
    "VALVE-77": {
        "status": "ok",
        "model": "mock-vision",
        "analysis": "Дефектов не обнаружено. Поверхности чистые, следов коррозии нет.",
        "defects": [],
    },
}

INSPECT_PROMPT = """Ты — инженер по надзору за оборудованием. По фотографии оцени состояние
промышленного узла {equipment} ({components}).

Верни ТОЛЬКО JSON без пояснений:
{{
  "status": "ok|medium|high",
  "analysis": "общий вывод на русском, 2-3 предложения",
  "defects": [
    {{
      "id": "D-LIVE-1",
      "node_id": "C1 или null",
      "type": "rust|crack|leak|wear",
      "title": "краткое название на русском",
      "confidence": 0.0-1.0,
      "severity": "low|medium|high",
      "bbox": [left, top, right, bottom],
      "analysis": "почему так, на русском",
      "recommendation": "что делать, на русском"
    }}
  ]
}}
bbox — координаты в долях кадра (0..1) от левого верхнего угла. Если дефектов нет — пустой массив."""

MOTTEL_PROMPT = """Ты — Моттэл, инженер-ассистент приложения AR-Инспектор. Ты одет строго:
тёмный костюм, круглые очки, галстук. Отвечаешь кратко, по делу, на русском,
по-инженерному спокойно. Не выдумывай факты, которых нет в контексте.
Если просят решение по дефекту — дай конкретные шаги и нужные запчасти.
Контекст оборудования:
{context}"""


def normalize_equipment_id(raw):
    if not isinstance(raw, str):
        return ""
    value = unquote(raw.strip())
    if not value:
        return ""
    if "://" in value:
        parts = [part for part in urlparse(value).path.split("/") if part]
        value = parts[-1] if parts else ""
    else:
        value = value.split("?", 1)[0].strip()
        if "/" in value:
            value = value.rstrip("/").rsplit("/", 1)[-1]
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,47}", value):
        return value.upper()
    match = re.search(r"([A-Z][A-Z0-9]{1,15}-\d{1,6})", value.upper())
    return match.group(1) if match else value.upper()[:48]


def repository_equipment(equipment_id):
    """Read the selected equipment from the active source of truth."""
    if PRODUCTION_MODE:
        if REPOSITORY is None:
            raise DatabaseError("persistent storage is unavailable")
        return REPOSITORY.get_equipment(equipment_id)
    return EQUIPMENT.get(equipment_id)


def decode_base64(value, max_bytes):
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError("base64 payload must be a string")
    if value.startswith("data:"):
        raise ValueError("base64 payload must not contain a data URL prefix")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("invalid base64 payload") from error
    if len(data) > max_bytes:
        raise ValueError("payload is too large")
    return data


def report_created_at(value):
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value


def report_id_for_today():
    return "ACT-" + datetime.now(timezone.utc).strftime("%y%m%d") + "-" + uuid.uuid4().hex[:4].upper()


def ensure_production_ready():
    if not PRODUCTION_MODE:
        return True
    if REPOSITORY is None:
        return configure_persistence()
    try:
        DATABASE.check_schema()
        return True
    except DatabaseError:
        return False


def upload_object(data, mime_type, key):
    if not data:
        return None
    if not OBJECT_STORAGE.configured:
        raise ObjectStorageError("object storage is not configured")
    return OBJECT_STORAGE.put_bytes(key, data, mime_type)


def cleanup_uploaded_object(object_info):
    """Remove an object that was uploaded before its DB transaction failed."""
    if object_info:
        OBJECT_STORAGE.delete(object_info["object_key"])


def production_dependency_status():
    """Check live production dependencies without exposing their credentials."""
    if not PRODUCTION_MODE:
        return None, None, None
    database_ok = False
    if ensure_production_ready():
        database_ok = True
    storage_ok = OBJECT_STORAGE.configured and OBJECT_STORAGE.check()
    ai_ok = False
    if LIVE_MODE:
        try:
            probe_timeout = max(0.5, min(float(os.getenv("LLM_HEALTH_TIMEOUT") or "3"), 10.0))
            request = Request(
                LLM_BASE_URL + "/models",
                headers={"Authorization": "Bearer " + LLM_API_KEY},
                method="GET",
            )
            with urlopen(request, timeout=probe_timeout) as response:
                ai_ok = 200 <= response.status < 300
        except Exception:
            ai_ok = False
    return database_ok, storage_ok, ai_ok


def active_equipment_catalog():
    if PRODUCTION_MODE:
        if REPOSITORY is None:
            return []
        try:
            return REPOSITORY.list_equipment()
        except DatabaseError:
            return []
    return [{"id": key, "name": value["name"]} for key, value in EQUIPMENT.items()]


# ---------------------------------------------------------------- LLM (live)


def call_llm(messages, max_tokens=900):
    """POST в OpenAI-совместимый /chat/completions. Возвращает текст ответа."""
    import urllib.request

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        LLM_BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + LLM_API_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=LLM_TIMEOUT) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def extract_json(text):
    """Модели любят обрамлять JSON ```-блоками и болтать вокруг."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = fenced.group(1) if fenced else text
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json in model answer")
    return json.loads(raw[start:end + 1])


def live_inspect(equipment_id, image_b64, aspect):
    equipment = repository_equipment(equipment_id)
    if equipment is None:
        raise RepositoryNotFound("equipment does not exist")
    components = ", ".join(f'{c["id"]}: {c["name"]}' for c in equipment["components"])
    prompt = INSPECT_PROMPT.format(equipment=equipment["name"], components=components)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}},
        ],
    }]
    result = extract_json(call_llm(messages))
    defects = []
    component_ids = {component["id"] for component in equipment["components"]}
    for index, item in enumerate(result.get("defects") or []):
        bbox = item.get("bbox") or [0.3, 0.3, 0.6, 0.6]
        if len(bbox) != 4 or any(not isinstance(v, (int, float)) for v in bbox):
            bbox = [0.3, 0.3, 0.6, 0.6]
        left, top, right, bottom = [min(max(float(v), 0.0), 1.0) for v in bbox]
        left, right = sorted((left, right))
        top, bottom = sorted((top, bottom))
        if left == right or top == bottom:
            left, top, right, bottom = 0.3, 0.3, 0.6, 0.6
        confidence = min(max(float(item.get("confidence") or 0.75), 0.0), 1.0)
        severity = (item.get("severity") or "medium").lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        node_id = item.get("node_id")
        if node_id not in component_ids:
            node_id = None
        defects.append({
            "id": item.get("id") or f"D-LIVE-{index + 1}",
            "node_id": node_id,
            "type": (item.get("type") or "rust").lower(),
            "title": item.get("title") or "Дефект",
            "confidence": confidence,
            "severity": severity,
            "bbox": [left, top, right, bottom],
            "polygon": [
                {"x": left, "y": top}, {"x": right, "y": top},
                {"x": right, "y": bottom}, {"x": left, "y": bottom},
            ],
            "analysis": item.get("analysis"),
            "recommendation": item.get("recommendation"),
        })
    severities = [d["severity"] for d in defects]
    status = "ok"
    if "high" in severities:
        status = "high"
    elif "medium" in severities:
        status = "medium"
    return {
        "status": status,
        "defects": defects,
        "analysis": result.get("analysis"),
        "model": LLM_MODEL,
    }


def live_chat(message, equipment_id, history):
    equipment = repository_equipment(equipment_id) if equipment_id else {}
    if equipment_id and equipment is None:
        raise RepositoryNotFound("equipment does not exist")
    context = json.dumps({
        "id": equipment.get("id"),
        "name": equipment.get("name"),
        "location": equipment.get("location"),
        "components": [
            {"id": c["id"], "name": c["name"], "description": c.get("description")}
            for c in equipment.get("components", [])
        ],
    }, ensure_ascii=False)
    messages = [{"role": "system", "content": MOTTEL_PROMPT.format(context=context)}]
    for turn in (history or [])[-8:]:
        role = "assistant" if turn.get("role") == "mottel" else "user"
        messages.append({"role": role, "content": str(turn.get("text") or "")[:2000]})
    messages.append({"role": "user", "content": message[:2000]})
    return call_llm(messages, max_tokens=600).strip()


# ---------------------------------------------------------------- Mock answers

MOTTEL_MOCK = [
    (("дефект", "находк", "что делать", "анализ"), (
        "По кадру три находки: коррозия фланца №3 (94%), трещина корпуса (87%) и лёгкая "
        "коррозия муфты (72%). Сначала фланец: снять давление, заменить прокладку, протянуть "
        "крепёж моментом 120 Н·м. Корпус — УЗК-контроль до следующего пуска."
    )),
    (("запчаст", "заказ", "купить"), (
        "Нужны: прокладка DN100 — 1 шт., болты М20×80 — 8 шт., преобразователь ржавчины — 1 л. "
        "Корпус насоса — только после УЗК, не заказывай заранее."
    )),
    (("акт", "отчёт", "отчет", "документ"), (
        "Акт собирается в карточке узла: выбери статус, добавь комментарий, нажми «Зафиксировать акт». "
        "Номер придёт с сервера, PDF можно отправить в мессенджер или на почту сразу с места."
    )),
    (("qr", "код", "скан"), (
        "QR на оборудовании — это адрес узла. Навёл камеру → паспорт с сервера → маркеры узлов "
        "встают на свои места относительно кода. Нужен свет и 20–30 см дистанции."
    )),
]

MOTTEL_FALLBACK = (
    "Я на связи. Могу разобрать найденные дефекты, собрать список запчастей, "
    "подсказать, как оформить акт. Спроси по делу — отвечу коротко."
)


def mock_chat(message):
    text = message.lower()
    for keys, answer in MOTTEL_MOCK:
        if any(key in text for key in keys):
            return answer
    return MOTTEL_FALLBACK


# ------------------------------------------------------------------- HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "ARInspector/2.0"

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))
        sys.stdout.flush()

    def _send(self, code, payload, content_type="application/json", headers=None):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = payload
        self.send_response(code)
        response_type = content_type
        if content_type.startswith("text/") or content_type == "application/json":
            response_type += "; charset=utf-8"
        self.send_header("Content-Type", response_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/health":
            database_ok, storage_ok, ai_ok = production_dependency_status()
            persistent_ok = database_ok and storage_ok and ai_ok if PRODUCTION_MODE else True
            return self._send(200 if persistent_ok else 503, {
                "status": "ok" if persistent_ok else "degraded",
                "mode": "live" if LIVE_MODE else "mock",
                "profile": APP_PROFILE,
                "persistence": "postgresql" if PRODUCTION_MODE else "memory",
                "database": (
                    "postgresql" if database_ok else "unavailable"
                ) if PRODUCTION_MODE else "not_required",
                "object_storage": (
                    "s3" if storage_ok else "unavailable"
                ) if PRODUCTION_MODE else "not_required",
                "ai": (
                    "live" if ai_ok else "not_configured"
                ) if PRODUCTION_MODE else ("live" if LIVE_MODE else "mock"),
                "model": model_name(),
                "time": now_iso(),
            })

        if path == "/api/reports":
            if PRODUCTION_MODE:
                if not ensure_production_ready():
                    return self._send(503, persistence_error_payload())
                try:
                    return self._send(200, {"reports": REPOSITORY.list_reports()})
                except DatabaseError:
                    return self._send(503, persistence_error_payload())
            with STATE_LOCK:
                reports = [
                    {
                        key: value
                        for key, value in report.items()
                        if key not in {"idempotency_key", "request_hash"}
                    }
                    for report in REPORTS
                ]
                return self._send(200, {"reports": reports})

        if path == "/api/equipment":
            if PRODUCTION_MODE:
                if not ensure_production_ready():
                    return self._send(503, persistence_error_payload())
                try:
                    return self._send(200, {"equipment": REPOSITORY.list_equipment()})
                except DatabaseError:
                    return self._send(503, persistence_error_payload())
            return self._send(200, {"equipment": [
                {"id": item["id"], "name": item["name"]} for item in EQUIPMENT.values()
            ]})

        match = re.fullmatch(r"/api/equipment/([^/]+)/documents/([^/]+)", path)
        if match:
            if not PRODUCTION_MODE:
                return self._send(404, {"error": "equipment document not found"})
            if not ensure_production_ready():
                return self._send(503, persistence_error_payload())
            equipment_id = normalize_equipment_id(unquote(match.group(1)))
            document_id = unquote(match.group(2))
            try:
                document = REPOSITORY.get_equipment_document(equipment_id, document_id)
            except RepositoryNotFound:
                return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
            except DatabaseError:
                return self._send(503, persistence_error_payload())
            if document is None or document.get("content") is None:
                return self._send(404, {"error": "equipment document not found"})
            safe_name = quote(str(document["file_name"]), safe="")
            return self._send(
                200,
                document["content"],
                str(document.get("mime_type") or "application/pdf"),
                {
                    "Content-Disposition": f"attachment; filename=passport.pdf; filename*=UTF-8''{safe_name}",
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "private, no-store",
                    "ETag": '"' + str(document.get("sha256") or "") + '"',
                },
            )

        match = re.fullmatch(r"/api/equipment/([^/]+)/documents", path)
        if match:
            if not PRODUCTION_MODE:
                return self._send(200, {"documents": []})
            if not ensure_production_ready():
                return self._send(503, persistence_error_payload())
            equipment_id = normalize_equipment_id(unquote(match.group(1)))
            try:
                documents = REPOSITORY.list_equipment_documents(equipment_id)
            except RepositoryNotFound:
                return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
            except DatabaseError:
                return self._send(503, persistence_error_payload())
            return self._send(200, {"documents": documents})

        match = re.fullmatch(r"/api/equipment/([^/]+)/telemetry", path)
        if match:
            equipment_id = normalize_equipment_id(match.group(1))
            if telemetry_service:
                return self._send(200, telemetry_service.get_current_reading(equipment_id))
            return self._send(200, {
                "equipment_id": equipment_id,
                "overall_status": "normal",
                "diagnosis": "Норма",
                "rpm": 2954.0,
                "channels": []
            })

        match = re.fullmatch(r"/api/equipment/([^/]+)", path)
        if match:
            equipment_id = normalize_equipment_id(match.group(1))
            if PRODUCTION_MODE:
                if not ensure_production_ready():
                    return self._send(503, persistence_error_payload())
                try:
                    data = REPOSITORY.get_equipment(equipment_id)
                except DatabaseError:
                    return self._send(503, persistence_error_payload())
                if data is None:
                    return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
            else:
                data = EQUIPMENT.get(equipment_id)
                if data is None:
                    data = {
                        "id": equipment_id,
                        "name": f"Оборудование {equipment_id}",
                        "location": "Зона не определена",
                        "components": EQUIPMENT["PUMP-402"]["components"],
                    }
            time.sleep(0.35)
            if isinstance(data, dict):
                data = dict(data)
                if telemetry_service:
                    data["telemetry"] = telemetry_service.get_current_reading(equipment_id)
            return self._send(200, data)

        match = re.fullmatch(r"/qr/([^/]+)", path)
        if match:
            return self._send(200, qr_page(match.group(1)), "text/html")

        if path == "/":
            return self._send(200, index_page(), "text/html")

        return self._send(404, {"error": "not found", "path": path})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._send(400, {"error": "invalid content length"})
        if length < 0:
            return self._send(400, {"error": "invalid content length"})
        if length > MAX_REQUEST_BYTES:
            return self._send(413, {"error": "request body is too large"})
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid json"})

        if path == "/api/inspect":
            return self._inspect(body)

        if path == "/api/chat":
            return self._chat(body)

        if path == "/api/reports":
            return self._create_report(body)

        match = re.fullmatch(r"/api/reports/([^/]+)/document", path)
        if match:
            return self._upload_report_document(unquote(match.group(1)), body)

        return self._send(404, {"error": "not found", "path": path})

    def _create_report(self, body):
        if not isinstance(body, dict):
            return self._send(400, {"error": "request body must be a JSON object"})
        equipment_id = normalize_equipment_id(body.get("equipment_id", ""))
        status = str(body.get("status") or "")
        if not equipment_id:
            return self._send(400, {"error": "equipment_id is required"})
        if status not in REPORT_STATUSES:
            return self._send(400, {
                "error": "invalid status",
                "allowed": sorted(REPORT_STATUSES),
            })
        body = dict(body)
        body["equipment_id"] = equipment_id
        body["status"] = status
        idempotency_key = (
            str(body.get("idempotency_key") or self.headers.get("Idempotency-Key") or "").strip()
        )
        if len(idempotency_key) > 200:
            return self._send(400, {"error": "Idempotency-Key is too long"})
        if idempotency_key:
            body["idempotency_key"] = idempotency_key

        if PRODUCTION_MODE:
            if not ensure_production_ready():
                return self._send(503, persistence_error_payload())
            try:
                digest = request_hash(body)
                existing = REPOSITORY.find_idempotent(idempotency_key)
                if existing:
                    if existing.get("request_hash") != digest:
                        return self._send(409, {"error": "idempotency key was used for another request"})
                    return self._send(200, {
                        "report_id": existing["report_id"],
                        "status": existing["resolution_status"],
                        "created_at": report_created_at(existing.get("created_at")),
                    })
                result = REPOSITORY.create_report(
                    body,
                    report_id_for_today(),
                    digest,
                )
                self.log_message("persistent report saved: %s status=%s", result["report_id"], status)
                return self._send(200, result)
            except RepositoryNotFound as error:
                return self._send(404, {"error": str(error)})
            except RepositoryConflict as error:
                return self._send(409, {"error": str(error)})
            except DatabaseError:
                return self._send(503, persistence_error_payload())

        with STATE_LOCK:
            digest = request_hash(body)
            if idempotency_key:
                for existing in REPORTS:
                    if existing.get("idempotency_key") == idempotency_key:
                        if existing.get("request_hash") != digest:
                            return self._send(409, {"error": "idempotency key was used for another request"})
                        return self._send(200, {
                            "report_id": existing["report_id"],
                            "status": existing["status"],
                            "created_at": existing["created_at"],
                        })
            report_id = report_id_for_today()
            entry = {
                "report_id": report_id,
                "equipment_id": equipment_id,
                "node_id": body.get("node_id"),
                "defect_id": body.get("defect_id"),
                "defect_title": body.get("defect_title"),
                "status": status,
                "comment": body.get("comment"),
                "created_at": now_iso(),
                "idempotency_key": idempotency_key or None,
                "request_hash": digest,
            }
            REPORTS.append(entry)
        time.sleep(0.5)
        self.log_message("report saved: %s status=%s", report_id, status)
        return self._send(200, {
            "report_id": report_id,
            "status": status,
            "created_at": entry["created_at"],
        })

    def _upload_report_document(self, report_id, body):
        if not PRODUCTION_MODE:
            return self._send(501, {"error": "document upload requires production profile"})
        if not ensure_production_ready():
            return self._send(503, persistence_error_payload())
        report_id = unquote(report_id)
        if REPORT_ID_RE.fullmatch(report_id) is None:
            return self._send(400, {"error": "invalid report_id"})
        if not isinstance(body, dict):
            return self._send(400, {"error": "request body must be a JSON object"})
        mime_type = str(body.get("mime_type") or "application/pdf").lower().strip()
        if mime_type != "application/pdf":
            return self._send(400, {"error": "only application/pdf is accepted"})
        try:
            content = decode_base64(body.get("file_base64"), MAX_DOCUMENT_BYTES)
        except ValueError as error:
            return self._send(400, {"error": str(error)})
        if not content:
            return self._send(400, {"error": "file_base64 is required"})
        if not (content.startswith(b"%PDF-") or content[:4] == b"%PDF"):
            return self._send(400, {"error": "file is not a PDF"})
        document_hash = hashlib.sha256(content).hexdigest()
        object_info = None
        try:
            existing = REPOSITORY.get_report_document(report_id)
            if existing is not None:
                if existing["sha256"] != document_hash:
                    return self._send(409, {"error": "report already has a different document"})
                return self._send(200, existing)
            object_info = upload_object(
                content,
                mime_type,
                f"reports/{report_id}/{uuid.uuid4().hex}.pdf",
            )
            result = REPOSITORY.attach_report_document(report_id, object_info)
            if result["object_key"] != object_info["object_key"]:
                cleanup_uploaded_object(object_info)
            return self._send(200, result)
        except RepositoryNotFound:
            cleanup_uploaded_object(object_info)
            return self._send(404, {"error": "report not found"})
        except RepositoryConflict as error:
            cleanup_uploaded_object(object_info)
            return self._send(409, {"error": str(error)})
        except ObjectStorageError:
            cleanup_uploaded_object(object_info)
            return self._send(503, {"error": "object storage unavailable"})
        except DatabaseError:
            cleanup_uploaded_object(object_info)
            return self._send(503, persistence_error_payload())

    # -- inspect
    def _inspect(self, body):
        if not isinstance(body, dict):
            return self._send(400, {"error": "request body must be a JSON object"})
        equipment_id = normalize_equipment_id(body.get("equipment_id", ""))
        image_b64 = body.get("image_base64")
        if image_b64 is not None and not isinstance(image_b64, str):
            return self._send(400, {"error": "image_base64 must be a string"})
        size_kb = round(len(image_b64) * 3 / 4 / 1024, 1) if image_b64 else 0
        self.log_message(
            "inspect: equipment=%s image=%s KB mode=%s",
            equipment_id, size_kb, "live" if LIVE_MODE else "mock",
        )

        if PRODUCTION_MODE:
            if not ensure_production_ready():
                return self._send(503, persistence_error_payload())
            try:
                equipment = REPOSITORY.get_equipment(equipment_id)
            except DatabaseError:
                return self._send(503, persistence_error_payload())
            if equipment is None:
                return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
            if not LIVE_MODE:
                return self._send(503, {"error": "vision service is not configured"})
            try:
                image_bytes = decode_base64(image_b64, MAX_IMAGE_BYTES)
            except ValueError as error:
                return self._send(400, {"error": str(error)})
            if not image_bytes:
                return self._send(400, {"error": "image_base64 is required in production"})
            if not image_bytes.startswith(b"\xff\xd8"):
                return self._send(400, {"error": "image must be a JPEG"})
            started = time.time()
            object_info = None
            try:
                payload = live_inspect(equipment_id, image_b64, body.get("screen_aspect"))
                payload["inspected_at"] = now_iso()
                object_info = upload_object(
                    image_bytes,
                    "image/jpeg",
                    f"inspections/{equipment_id}/raw/{uuid.uuid4().hex}.jpg",
                )
                inspection_id = REPOSITORY.persist_inspection(equipment, payload, object_info)
                payload["inspection_id"] = inspection_id
                self.log_message(
                    "persistent inspection %s: %s defects in %.1f s",
                    inspection_id, len(payload["defects"]), time.time() - started,
                )
                return self._send(200, payload)
            except RepositoryNotFound:
                cleanup_uploaded_object(object_info)
                return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
            except ObjectStorageError:
                cleanup_uploaded_object(object_info)
                return self._send(503, {"error": "object storage unavailable"})
            except DatabaseError:
                cleanup_uploaded_object(object_info)
                return self._send(503, persistence_error_payload())
            except Exception as error:
                cleanup_uploaded_object(object_info)
                self.log_message("LIVE FAILED in production: %s", error)
                return self._send(503, {"error": "vision service unavailable"})

        if LIVE_MODE and image_b64:
            started = time.time()
            try:
                payload = live_inspect(equipment_id, image_b64, body.get("screen_aspect"))
                payload["inspected_at"] = now_iso()
                self.log_message(
                    "live ok: %s дефектов за %.1f c",
                    len(payload["defects"]), time.time() - started,
                )
                return self._send(200, payload)
            except Exception as error:  # сеть, ключ, формат ответа модели
                self.log_message("LIVE FAILED (%s) -> mock", error)

        time.sleep(1.4)
        scenario = DEFECTS.get(equipment_id, DEFECTS["PUMP-402"])
        payload = json.loads(json.dumps(scenario))
        payload["model"] = model_name()
        payload["inspected_at"] = now_iso()
        payload["jitter"] = round(random.uniform(0, 1), 3)
        return self._send(200, payload)

    # -- chat (Моттэл)
    def _chat(self, body):
        if not isinstance(body, dict):
            return self._send(400, {"error": "request body must be a JSON object"})
        message_value = body.get("message")
        if message_value is not None and not isinstance(message_value, str):
            return self._send(400, {"error": "message must be a string"})
        message = (message_value or "").strip()
        if not message:
            return self._send(400, {"error": "empty message"})
        equipment_id = normalize_equipment_id(body.get("equipment_id", ""))
        self.log_message("chat: equipment=%s chars=%s", equipment_id, len(message))

        if PRODUCTION_MODE:
            if not ensure_production_ready():
                return self._send(503, persistence_error_payload())
            if equipment_id:
                try:
                    if REPOSITORY.get_equipment(equipment_id) is None:
                        return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
                except DatabaseError:
                    return self._send(503, persistence_error_payload())
            if not LIVE_MODE:
                return self._send(503, {"error": "assistant service is not configured"})
            try:
                answer = live_chat(message, equipment_id, body.get("history"))
                return self._send(200, {"reply": answer, "model": LLM_MODEL})
            except RepositoryNotFound:
                return self._send(404, {"error": "equipment not found", "equipment_id": equipment_id})
            except Exception as error:
                self.log_message("chat failed in production (%s)", type(error).__name__)
                return self._send(503, {"error": "assistant service unavailable"})

        if LIVE_MODE:
            try:
                answer = live_chat(message, equipment_id, body.get("history"))
                return self._send(200, {"reply": answer, "model": LLM_MODEL})
            except Exception as error:
                self.log_message("chat live failed (%s) -> mock", error)

        time.sleep(0.4)
        return self._send(200, {"reply": mock_chat(message), "model": "mock-assistant"})


def qr_page(equipment_id):
    """Страница с QR: открывается на ноутбуке, сканируется телефоном."""
    equipment_id = normalize_equipment_id(equipment_id)
    safe_equipment_id = escape(equipment_id)
    js_equipment_id = json.dumps(equipment_id, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>QR · {safe_equipment_id}</title>
<style>
  body {{ margin:0; min-height:100vh; display:grid; place-items:center;
         background:#070a0c; color:#eaf2f5;
         font-family: ui-monospace, Consolas, monospace; }}
  .card {{ padding:32px 40px; border:1px solid #2a363d; background:#101619;
           box-shadow: 0 0 60px rgba(53,214,232,.08); text-align:center; }}
  .t {{ color:#ffc400; letter-spacing:.18em; font-size:13px; margin-bottom:18px; }}
  #qr {{ width:340px; height:340px; background:#fff; padding:14px; }}
  .id {{ margin-top:16px; font-size:26px; font-weight:700; letter-spacing:.1em; }}
  .h {{ color:#8fa3ac; font-size:12px; margin-top:8px; }}
</style></head>
<body>
<div class="card">
  <div class="t">AR · ИНСПЕКТОР — КИБЕР 102</div>
  <img id="qr" alt="QR {safe_equipment_id}">
  <div class="id">{safe_equipment_id}</div>
  <div class="h">наведите камеру приложения на этот код</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
  new QRCode(document.getElementById('qr'), {{
     text: {js_equipment_id}, width: 320, height: 320,
    colorDark: '#070a0c', colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.H
  }});
</script>
</body></html>"""


def index_page():
    catalog = active_equipment_catalog()
    ids = "".join(
        f'<li><a href="/qr/{escape(str(item["id"]))}">{escape(str(item["id"]))}</a> — '
        f'{escape(str(item["name"]))}</li>'
        for item in catalog
    )
    mode = ("LIVE · " + LLM_MODEL if LIVE_MODE else "MOCK") + " · " + APP_PROFILE
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>AR-Инспектор · API</title>
<style>
 body{{background:#070a0c;color:#eaf2f5;font-family:ui-monospace,Consolas,monospace;padding:40px;line-height:1.7}}
 a{{color:#35d6e8}} h1{{color:#ffc400;font-size:20px;letter-spacing:.12em}}
 code{{color:#37e08f}} .mode{{color:#37e08f}}
</style></head><body>
<h1>AR-ИНСПЕКТОР · API</h1>
<p class="mode">Режим: {mode}</p>
<pre>GET  /api/health
GET  /api/equipment/{{id}}
POST /api/inspect
POST /api/chat
POST /api/reports
GET  /api/reports</pre>
<p>QR-коды для сканирования:</p><ul>{ids}</ul>
<p>Эмулятор видит хост как <code>http://10.0.2.2:8080/</code>.
Телефон — как <code>http://&lt;IP-ноутбука&gt;:8080/</code>.</p>
</body></html>"""


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    if PRODUCTION_MODE:
        if configure_persistence():
            print("  PostgreSQL: connected")
        else:
            print("  PostgreSQL: unavailable (API will return 503; no mock fallback)")
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("=" * 62)
    print("  AR-ИНСПЕКТОР · API")
    print(f"  профиль: {APP_PROFILE}")
    print(f"  режим: {'LIVE · ' + LLM_MODEL if LIVE_MODE else 'MOCK (без сети и ключей)'}")
    print(f"  http://localhost:{port}/            (QR-страницы для демо)")
    print(f"  http://localhost:{port}/api/health  (проверка)")
    print("  Ctrl+C — остановить")
    print("=" * 62)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nостановлено")
        server.shutdown()
    finally:
        if DATABASE is not None:
            DATABASE.close()


if __name__ == "__main__":
    main()
