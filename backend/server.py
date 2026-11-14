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
from urllib.parse import unquote, urlparse

# Консоль Windows часто в cp1251: без этого печать падала на любом символе.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

STATE_LOCK = threading.Lock()
REPORTS = []

LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL") or "gpt-4o-mini"
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT") or 45)
LIVE_MODE = bool(LLM_BASE_URL and LLM_API_KEY)


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
    # QR часто содержит ссылку: пробелы и дефисы в ней приходят как %20 и %2D.
    raw = unquote(raw or "")
    match = re.search(r"([A-Z][A-Z0-9]{1,15}-\d{1,6})", raw.upper())
    return match.group(1) if match else (raw.strip().upper()[:48])


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
    equipment = EQUIPMENT.get(equipment_id) or EQUIPMENT["PUMP-402"]
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
    for index, item in enumerate(result.get("defects") or []):
        bbox = item.get("bbox") or [0.3, 0.3, 0.6, 0.6]
        if len(bbox) != 4 or any(not isinstance(v, (int, float)) for v in bbox):
            bbox = [0.3, 0.3, 0.6, 0.6]
        left, top, right, bottom = [min(max(float(v), 0.0), 1.0) for v in bbox]
        defects.append({
            "id": item.get("id") or f"D-LIVE-{index + 1}",
            "node_id": item.get("node_id"),
            "type": (item.get("type") or "rust").lower(),
            "title": item.get("title") or "Дефект",
            "confidence": float(item.get("confidence") or 0.75),
            "severity": (item.get("severity") or "medium").lower(),
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
    equipment = EQUIPMENT.get(equipment_id) or {}
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

    def _send(self, code, payload, content_type="application/json"):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = payload
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"

        if path == "/api/health":
            return self._send(200, {
                "status": "ok",
                "mode": "live" if LIVE_MODE else "mock",
                "model": model_name(),
                "time": now_iso(),
            })

        if path == "/api/reports":
            with STATE_LOCK:
                return self._send(200, {"reports": list(REPORTS)})

        match = re.fullmatch(r"/api/equipment/([^/]+)", path)
        if match:
            equipment_id = normalize_equipment_id(match.group(1))
            data = EQUIPMENT.get(equipment_id)
            if data is None:
                data = {
                    "id": equipment_id,
                    "name": f"Оборудование {equipment_id}",
                    "location": "Зона не определена",
                    "components": EQUIPMENT["PUMP-402"]["components"],
                }
            time.sleep(0.35)
            return self._send(200, data)

        match = re.fullmatch(r"/qr/([^/]+)", path)
        if match:
            return self._send(200, qr_page(match.group(1)), "text/html")

        if path == "/":
            return self._send(200, index_page(), "text/html")

        return self._send(404, {"error": "not found", "path": path})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")
        length = int(self.headers.get("Content-Length") or 0)
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
            with STATE_LOCK:
                report_id = "ACT-" + datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:4].upper()
                entry = {
                    "report_id": report_id,
                    "equipment_id": body.get("equipment_id"),
                    "node_id": body.get("node_id"),
                    "defect_id": body.get("defect_id"),
                    "defect_title": body.get("defect_title"),
                    "status": body.get("status"),
                    "comment": body.get("comment"),
                    "created_at": now_iso(),
                }
                REPORTS.append(entry)
            time.sleep(0.5)
            self.log_message("report saved: %s status=%s", report_id, entry["status"])
            return self._send(200, {
                "report_id": report_id,
                "status": entry["status"],
                "created_at": entry["created_at"],
            })

        return self._send(404, {"error": "not found", "path": path})

    # -- inspect
    def _inspect(self, body):
        equipment_id = normalize_equipment_id(body.get("equipment_id", ""))
        image_b64 = body.get("image_base64")
        size_kb = round(len(image_b64) * 3 / 4 / 1024, 1) if image_b64 else 0
        self.log_message(
            "inspect: equipment=%s image=%s KB mode=%s",
            equipment_id, size_kb, "live" if LIVE_MODE else "mock",
        )

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
        message = (body.get("message") or "").strip()
        if not message:
            return self._send(400, {"error": "empty message"})
        equipment_id = normalize_equipment_id(body.get("equipment_id", ""))
        self.log_message("chat: equipment=%s msg=%s", equipment_id, message[:80])

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
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>QR · {equipment_id}</title>
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
  <img id="qr" alt="QR {equipment_id}">
  <div class="id">{equipment_id}</div>
  <div class="h">наведите камеру приложения на этот код</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>
  new QRCode(document.getElementById('qr'), {{
    text: '{equipment_id}', width: 320, height: 320,
    colorDark: '#070a0c', colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.H
  }});
</script>
</body></html>"""


def index_page():
    ids = "".join(
        f'<li><a href="/qr/{i}">{i}</a> — {EQUIPMENT[i]["name"]}</li>' for i in EQUIPMENT
    )
    mode = "LIVE · " + LLM_MODEL if LIVE_MODE else "MOCK"
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
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("=" * 62)
    print("  AR-ИНСПЕКТОР · API")
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


if __name__ == "__main__":
    main()
