#!/usr/bin/env python3
"""Проверка демо-цепочки «AR-Инспектор» перед питчем.

Запускает `backend/server.py` на свободном порту и проверяет не «что-то ответило»,
а контракт из `docs/API.md` в тех местах, где приложение ломается молча:

  * `components[].offset_from_qr` — без него AR не расставит маркеры узлов;
  * `defects[].node_id` — должен ссылаться на существующий узел;
  * `polygon` / `bbox` — только нормализованные 0..1, иначе Canvas нарисует мимо;
  * `status` и `severity` — значения, которые приложение умеет красить;
  * `report_id` — формат, который печатается в PDF-акте;
  * пустой сценарий (`VALVE-77`) — у приложения есть отдельное состояние «дефектов нет».

Зависимостей нет: только стандартная библиотека Python 3.

    python tools/verify_demo.py                 # поднять мок и проверить
    python tools/verify_demo.py --url http://localhost:8080   # проверить уже запущенный
    python tools/verify_demo.py --image photo.jpg             # с настоящим кадром (live)

Код возврата 0 — всё в порядке, 1 — есть провалы. Печатать это в CI и перед сценой.
"""

import argparse
import base64
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "backend" / "server.py"

# 1x1 JPEG: мок его не читает, но в live-режиме нужен настоящий кадр (--image).
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)

STATUSES = {"ok", "medium", "high"}
SEVERITIES = {"low", "medium", "high"}
REPORT_STATUSES = ("fixed_on_site", "parts_required", "false_positive")

failures = 0
warnings = 0


def line(tag, name, detail=""):
    """Одна строка отчёта. Вывод намеренно ASCII: консоль Windows ломает кириллицу."""
    pad = "." * max(2, 34 - len(name))
    print(f"  [{tag:^4}] {name} {pad} {detail}".rstrip())


def ok(name, detail=""):
    line("OK", name, detail)


def fail(name, detail):
    global failures
    failures += 1
    line("FAIL", name, detail)


def warn(name, detail):
    global warnings
    warnings += 1
    line("WARN", name, detail)


def skip(name, detail):
    line("SKIP", name, detail)


# ------------------------------------------------------------------ HTTP


class Response:
    def __init__(self, status, body, headers):
        self.status = status
        self.raw = body
        self.headers = headers
        try:
            self.json = json.loads(body.decode("utf-8"))
        except Exception:
            self.json = None

    def text(self):
        return self.raw.decode("utf-8", "replace")


def request(base, path, method="GET", payload=None, timeout=120):
    url = base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, resp.read(), dict(resp.headers))
    except urllib.error.HTTPError as error:
        return Response(error.code, error.read(), dict(error.headers))
    except Exception as error:
        raise RuntimeError(f"{method} {path}: {error}") from error


# ------------------------------------------------------------------ helpers


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server(port):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        creationflags=creation,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 25
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"backend exited with code {proc.returncode}")
        try:
            if request(base, "/api/health", timeout=3).status == 200:
                return proc, base
        except RuntimeError:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("backend did not answer /api/health in 25s")


# ------------------------------------------------------------------ checks


def check_health(base):
    resp = request(base, "/api/health")
    if resp.status != 200:
        return fail("health", f"HTTP {resp.status}")
    body = resp.json or {}
    if body.get("status") != "ok":
        return fail("health", f"status={body.get('status')!r}")
    if body.get("mode") not in ("mock", "live"):
        return fail("health", f"mode={body.get('mode')!r}")
    if not body.get("model"):
        return fail("health", "model is empty")
    if not body.get("time"):
        return fail("health", "time is empty")
    ok("health", f"mode={body['mode']} model={body['model']}")


def fetch_equipment(base, equipment_id):
    resp = request(base, f"/api/equipment/{equipment_id}")
    if resp.status != 200 or not resp.json:
        fail("equipment " + equipment_id, f"HTTP {resp.status}")
        return None
    return resp.json


def check_equipment(base, equipment_id, required=True):
    data = fetch_equipment(base, equipment_id)
    if data is None:
        return None
    if data.get("id") != equipment_id:
        fail("equipment " + equipment_id, f"id={data.get('id')!r}")
        return data
    if not data.get("name") or not data.get("location"):
        fail("equipment " + equipment_id, "name/location is empty")
        return data
    components = data.get("components")
    if not isinstance(components, list) or not components:
        fail("equipment " + equipment_id, "components is empty")
        return data
    ok("equipment " + equipment_id, f"{len(components)} components")
    return data


def check_components_contract(data, equipment_id):
    """offset_from_qr и radius — единственное, на чём держится AR-схема."""
    seen = set()
    for comp in data.get("components", []):
        cid = comp.get("id")
        if not isinstance(cid, str) or not cid:
            return fail("components." + equipment_id, "component without id")
        if cid in seen:
            return fail("components." + equipment_id, f"duplicate node id {cid}")
        seen.add(cid)
        if not comp.get("name"):
            return fail("components." + equipment_id, f"{cid}: name is empty")
        offset = comp.get("offset_from_qr")
        if not isinstance(offset, dict):
            return fail("components." + equipment_id, f"{cid}: no offset_from_qr (AR marker lost)")
        for axis in ("x", "y", "z"):
            if not is_number(offset.get(axis)):
                return fail("components." + equipment_id, f"{cid}: offset.{axis} not a number")
        radius = comp.get("radius")
        if not is_number(radius) or radius <= 0:
            return fail("components." + equipment_id, f"{cid}: radius must be > 0")
    ok("components contract", f"{len(seen)} nodes with offsets")


def check_normalization(base):
    """ID из QR может прийти с пробелами, URL-кодированием или как полная ссылка."""
    probes = {
        "/api/equipment/%20%20PUMP-402%20%20": "PUMP-402",
        "/api/equipment/pump-402": "PUMP-402",
        "/api/equipment/PUMP%2D402": "PUMP-402",
    }
    for path, expected in probes.items():
        resp = request(base, path)
        got = (resp.json or {}).get("id")
        if resp.status != 200 or got != expected:
            return fail("id normalization", f"{path} -> {got!r}, expected {expected}")
    ok("id normalization", f"{len(probes)} variants")

    # QR на незнакомом оборудовании не должен ронять демо: приложение ждёт AR-схему.
    resp = request(base, "/api/equipment/ZZZ-9")
    body = resp.json or {}
    if resp.status != 200 or not body.get("components"):
        return fail("unknown equipment", f"HTTP {resp.status}, components missing")
    ok("unknown equipment", f"fallback with {len(body['components'])} components")


def check_inspect(base, equipment_id, image_bytes):
    payload = {
        "equipment_id": equipment_id,
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "screen_aspect": 0.462,
        "image_width": 960,
        "image_height": 2077,
    }
    resp = request(base, "/api/inspect", "POST", payload)
    if resp.status != 200 or not resp.json:
        fail("inspect " + equipment_id, f"HTTP {resp.status}")
        return None
    body = resp.json
    if body.get("status") not in STATUSES:
        fail("inspect " + equipment_id, f"status={body.get('status')!r}")
        return None
    if not isinstance(body.get("defects"), list):
        fail("inspect " + equipment_id, "defects is not a list")
        return None
    if not isinstance(body.get("analysis"), str) or not body["analysis"].strip():
        fail("inspect " + equipment_id, "analysis is empty")
        return None
    if not body.get("inspected_at") or not body.get("model"):
        fail("inspect " + equipment_id, "inspected_at/model is empty")
        return None
    ok("inspect " + equipment_id, f"status={body['status']} defects={len(body['defects'])}")
    return body


def check_defects(body, component_ids):
    """Поля дефекта, которые рисует Canvas и красит 3D-маркер."""
    defects = body.get("defects", [])
    if not defects:
        return ok("defect fields", "no defects in this scenario")

    ids = set()
    for defect in defects:
        did = defect.get("id")
        label = did or "<no id>"
        if not isinstance(did, str) or not did:
            return fail("defect fields", "defect without id")
        if did in ids:
            return fail("defect fields", f"duplicate defect id {did}")
        ids.add(did)
        for field in ("type", "title", "analysis", "recommendation"):
            if not isinstance(defect.get(field), str) or not defect[field].strip():
                return fail("defect fields", f"{label}: {field} is empty")
        confidence = defect.get("confidence")
        if not is_number(confidence) or not 0.0 <= confidence <= 1.0:
            return fail("defect fields", f"{label}: confidence={confidence!r} not in 0..1")
        if defect.get("severity") not in SEVERITIES:
            return fail("defect fields", f"{label}: severity={defect.get('severity')!r}")

        node_id = defect.get("node_id")
        if node_id is not None and node_id not in component_ids:
            return fail("defect -> node", f"{label}: node_id={node_id!r} not in components (marker stays grey)")

        points = defect.get("polygon")
        box = defect.get("bbox")
        if points is None and box is None:
            return fail("defect geometry", f"{label}: neither polygon nor bbox (nothing to draw)")
        if points is not None:
            if not isinstance(points, list) or len(points) < 3:
                return fail("defect geometry", f"{label}: polygon needs >= 3 points")
            for point in points:
                if not isinstance(point, dict):
                    return fail("defect geometry", f"{label}: polygon point is not an object")
                for axis in ("x", "y"):
                    value = point.get(axis)
                    if not is_number(value) or not 0.0 <= value <= 1.0:
                        return fail("defect geometry", f"{label}: point.{axis}={value!r} not normalized")
        if box is not None:
            if not isinstance(box, list) or len(box) != 4:
                return fail("defect geometry", f"{label}: bbox must be [left, top, right, bottom]")
            left, top, right, bottom = box
            if not all(is_number(v) and 0.0 <= v <= 1.0 for v in box):
                return fail("defect geometry", f"{label}: bbox values not normalized")
            if left >= right or top >= bottom:
                return fail("defect geometry", f"{label}: bbox is degenerate")
    ok("defect fields", f"{len(defects)} defects, geometry + nodes checked")


def check_demo_scenario(body, equipment_id):
    """Сценарий питча: на экране должны быть красные маркеры, а не «всё чисто»."""
    if equipment_id != "PUMP-402":
        return
    defects = body.get("defects", [])
    hot = [d for d in defects if d.get("severity") == "high"]
    if body.get("status") != "high":
        return fail("demo scenario", f"PUMP-402 status={body.get('status')!r}, expected 'high'")
    if not hot:
        return fail("demo scenario", "PUMP-402 has no high-severity defect (no red markers)")
    ok("demo scenario", f"status=high, {len(hot)} red defects")


def check_empty_state(base, image_bytes):
    body = check_inspect(base, "VALVE-77", image_bytes)
    if body is None:
        return
    if body.get("defects"):
        return fail("empty state", f"VALVE-77 returned {len(body['defects'])} defects")
    if body.get("status") != "ok":
        return fail("empty state", f"VALVE-77 status={body.get('status')!r}")
    ok("empty state", "ok, no defects")


def check_reports(base):
    created = {}
    for status in REPORT_STATUSES:
        payload = {
            "equipment_id": "PUMP-402",
            "node_id": "C3",
            "defect_id": "D-402-1",
            "defect_title": "Коррозия фланцевого соединения",
            "status": status,
            "comment": "verify_demo.py",
            "created_at": "2026-11-14T10:00:00Z",
            "source": "verify_demo",
        }
        resp = request(base, "/api/reports", "POST", payload)
        if resp.status != 200 or not resp.json:
            return fail("report create", f"status={status}: HTTP {resp.status}")
        body = resp.json
        report_id = body.get("report_id")
        if not isinstance(report_id, str) or not re.fullmatch(r"ACT-\d{6}-[0-9A-F]{4}", report_id):
            return fail("report create", f"report_id={report_id!r} does not match ACT-YYMMDD-XXXX")
        if body.get("status") != status:
            return fail("report create", f"status not echoed: {body.get('status')!r} != {status}")
        if not body.get("created_at"):
            return fail("report create", "created_at is empty")
        created[report_id] = status
    ok("report create", f"{len(created)} statuses, ids like {sorted(created)[0]}")

    resp = request(base, "/api/reports")
    if resp.status != 200 or not isinstance((resp.json or {}).get("reports"), list):
        return fail("report list", f"HTTP {resp.status}")
    stored = {r.get("report_id") for r in resp.json["reports"]}
    missing = set(created) - stored
    if missing:
        return fail("report list", f"not returned: {sorted(missing)}")
    ok("report list", f"{len(stored)} reports stored")


def check_chat(base):
    resp = request(base, "/api/chat", "POST", {
        "message": "Что делать с находками?",
        "equipment_id": "PUMP-402",
        "history": [{"role": "user", "text": "Привет"}],
    })
    if resp.status != 200 or not resp.json:
        return fail("chat", f"HTTP {resp.status}")
    reply = resp.json.get("reply")
    if not isinstance(reply, str) or len(reply.strip()) < 15:
        return fail("chat", f"reply is empty or too short: {reply!r}")
    if not resp.json.get("model"):
        return fail("chat", "model is empty")
    ok("chat", f"{len(reply)} chars, model={resp.json['model']}")

    resp = request(base, "/api/chat", "POST", {"message": "   "})
    if resp.status != 400:
        return fail("chat validation", f"empty message -> HTTP {resp.status}, expected 400")
    ok("chat validation", "empty message rejected with 400")


def check_pages(base):
    resp = request(base, "/qr/PUMP-402")
    if resp.status != 200 or "PUMP-402" not in resp.text():
        return fail("qr page", f"HTTP {resp.status}")
    if "text/html" not in resp.headers.get("Content-Type", ""):
        return fail("qr page", f"content-type={resp.headers.get('Content-Type')!r}")
    ok("qr page", "200 html with equipment id")

    resp = request(base, "/")
    if resp.status != 200 or "PUMP-402" not in resp.text():
        return fail("index page", f"HTTP {resp.status}")
    ok("index page", "200 html with equipment list")


def check_cors(base):
    resp = request(base, "/api/health")
    allowed = resp.headers.get("Access-Control-Allow-Origin")
    if allowed != "*":
        return fail("cors", f"Access-Control-Allow-Origin={allowed!r}")
    ok("cors", "*")


# ------------------------------------------------------------------ main


def main():
    parser = argparse.ArgumentParser(description="Проверка демо-цепочки AR-Инспектора")
    parser.add_argument("--url", help="проверить уже запущенный бэкенд вместо запуска своего")
    parser.add_argument("--image", help="настоящий кадр для live-режима (по умолчанию 1x1 заглушка)")
    parser.add_argument("--quiet-start", action="store_true", help="не печатать адрес бэкенда")
    args = parser.parse_args()

    if args.image:
        image_bytes = Path(args.image).read_bytes()
        if not image_bytes:
            print(f"пустой файл: {args.image}")
            return 1
    else:
        image_bytes = TINY_JPEG

    proc = None
    if args.url:
        base = args.url.rstrip("/")
        if not args.quiet_start:
            print(f"Target: {base}")
    else:
        if not SERVER.exists():
            print(f"не найден {SERVER}")
            return 1
        port = free_port()
        try:
            proc, base = start_server(port)
        except RuntimeError as error:
            print(f"не удалось запустить бэкенд: {error}")
            return 1
        if not args.quiet_start:
            print(f"Backend: {base} (PID {proc.pid})")

    print("\nContract checks (docs/API.md):")
    try:
        check_health(base)

        pump = check_equipment(base, "PUMP-402")
        if pump:
            check_components_contract(pump, "PUMP-402")
        component_ids = {c.get("id") for c in (pump or {}).get("components", [])}

        check_equipment(base, "PUMP-118")
        check_equipment(base, "VALVE-77")
        check_normalization(base)

        body = check_inspect(base, "PUMP-402", image_bytes)
        if body:
            check_defects(body, component_ids)
            check_demo_scenario(body, "PUMP-402")

        check_empty_state(base, image_bytes)
        check_reports(base)
        check_chat(base)
        check_pages(base)
        check_cors(base)
    except RuntimeError as error:
        fail("transport", str(error))
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    total = failures + warnings
    print()
    if failures:
        print(f"RESULT: {failures} failed, {warnings} warnings")
        print("Демо не готово: исправь провалы выше, потом показывай жюри.")
        return 1
    if warnings:
        print(f"RESULT: 0 failed, {warnings} warnings - демо работает, но есть мелочи.")
        return 0
    print("RESULT: all checks passed - цепочка QR -> AR -> ИИ -> акт отвечает по контракту.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
