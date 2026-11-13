#!/usr/bin/env python3
"""
Мок-бэкенд AR-Инспектор (Кибер 102).

Запуск:
    python backend/server.py            # порт 8080, слушает 0.0.0.0
    python backend/server.py 9000       # другой порт

Эндпоинты (контракт в docs/API.md):
    GET  /api/equipment/{id}   — схема оборудования с components[]
    POST /api/inspect          — приём кадра, возврат дефектов в нормализованных координатах
    POST /api/reports          — сохранение акта, возврат report_id
    GET  /api/reports          — список сохранённых актов
    GET  /api/health           — проверка живости
    GET  /qr/{id}              — HTML-страница с QR-кодом для демонстрации со второго экрана

Зависимостей нет — только стандартная библиотека.
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
from urllib.parse import urlparse

# Консоль Windows часто в cp1251: без этого печать «↳» роняет обработчик запроса.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

STATE_LOCK = threading.Lock()
REPORTS = []

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

# Сценарий дефектов: одинаковый для демо, чтобы питч был предсказуемым.
DEFECTS = {
    "PUMP-402": {
        "status": "high",
        "model": "demo-llm-vision",
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
                    "На поверхности фланца №3 обнаружена очаговая коррозия с локальной потерей сечения "
                    "до 12%. Наиболее вероятная причина — разрушение прокладки и постоянный контакт с "
                    "влажной средой. Риск: потеря герметичности и разгерметизация соединения под давлением."
                ),
                "recommendation": (
                    "Зачистить поверхность до металла, заменить прокладку, протянуть крепёж моментом "
                    "120 Н·м. Повторный осмотр через 72 часа."
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
                    "Линейный дефект длиной ~38 мм с branching-паттерном, характерным для усталостной "
                    "трещины. Расположен в зоне концентрации напряжений у опорного пояса. Требует "
                    "немедленной разгрузки узла."
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
                    "Поверхностная коррозия без признаков потери сечения. На эксплуатацию влияет слабо, "
                    "но требует защиты покрытием."
                ),
                "recommendation": "Обработать преобразователем ржавчины и покрыть защитным составом.",
            },
        ],
    },
    "PUMP-118": {
        "status": "medium",
        "model": "demo-llm-vision",
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
        "model": "demo-llm-vision",
        "analysis": "Дефектов не обнаружено. Поверхности чистые, следов коррозии нет.",
        "defects": [],
    },
}


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_equipment_id(raw):
    match = re.search(r"([A-Z][A-Z0-9]{1,15}-\d{1,6})", (raw or "").upper())
    return match.group(1) if match else (raw or "").strip().upper()[:48]


class Handler(BaseHTTPRequestHandler):
    server_version = "ARInspectorMock/1.0"

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
            return self._send(200, {"status": "ok", "time": now_iso()})

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
            equipment_id = normalize_equipment_id(body.get("equipment_id", ""))
            image_b64 = body.get("image_base64")
            size_kb = round(len(image_b64) * 3 / 4 / 1024, 1) if image_b64 else 0
            sys.stdout.write(
                f"  -> inspect: equipment={equipment_id} image={size_kb} KB "
                f"aspect={body.get('screen_aspect')}\n"
            )
            sys.stdout.flush()
            time.sleep(1.4)  # имитация работы vision-модели
            scenario = DEFECTS.get(equipment_id, DEFECTS["PUMP-402"])
            payload = dict(scenario)
            payload["inspected_at"] = now_iso()
            payload["jitter"] = round(random.uniform(0, 1), 3)
            return self._send(200, payload)

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
            sys.stdout.write(f"  -> report saved: {report_id} status={entry['status']}\n")
            sys.stdout.flush()
            return self._send(200, {
                "report_id": report_id,
                "status": entry["status"],
                "created_at": entry["created_at"],
            })

        return self._send(404, {"error": "not found", "path": path})


def qr_page(equipment_id):
    """Страница с QR-кодом: открывается на ноутбуке, сканируется телефоном."""
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
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>AR-Инспектор · mock API</title>
<style>
 body{{background:#070a0c;color:#eaf2f5;font-family:ui-monospace,Consolas,monospace;padding:40px;line-height:1.7}}
 a{{color:#35d6e8}} h1{{color:#ffc400;font-size:20px;letter-spacing:.12em}}
 code{{color:#37e08f}}
</style></head><body>
<h1>AR-ИНСПЕКТОР · MOCK API</h1>
<p>Живой бэкенд для демо. Эндпоинты:</p>
<pre>GET  /api/health
GET  /api/equipment/{{id}}
POST /api/inspect
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
    print("  AR-ИНСПЕКТОР · MOCK API")
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
