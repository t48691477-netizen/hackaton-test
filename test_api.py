import sys
import os
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("AG_LS_PROXY", None)

import io
import json
from pathlib import Path
from PIL import Image, ImageDraw
from starlette.testclient import TestClient

# Добавляем путь проекта
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.main import app

client = TestClient(app)

def test_full_pipeline():
    print("=== 1. Проверка корневого эндпоинта и Swagger docs ===")
    r = client.get("/")
    assert r.status_code == 200, f"Root error: {r.text}"
    print("Root response:", r.json())

    r_docs = client.get("/docs")
    assert r_docs.status_code == 200, "Swagger UI не доступен!"
    print("Swagger UI (/docs) доступен: OK (status 200)")

    r_openapi = client.get("/openapi.json")
    assert r_openapi.status_code == 200, "openapi.json не доступен!"
    print("OpenAPI spec доступна: OK")

    print("\n=== 2. Проверка GET /api/equipment ===")
    r = client.get("/api/equipment")
    assert r.status_code == 200
    eq_list = r.json()
    print(f"Получено оборудования: {len(eq_list)}")
    assert len(eq_list) > 0
    target_eq_id = eq_list[0]["id"]
    print(f"Тестовый агрегат ID: {target_eq_id}, имя: {eq_list[0]['name']}")

    print("\n=== 3. Проверка GET /api/equipment/{id} ===")
    r = client.get(f"/api/equipment/{target_eq_id}")
    assert r.status_code == 200
    card = r.json()
    print(f"Карточка агрегата: {card['name']}, узлов: {len(card['components'])}")
    for comp in card['components']:
        print(f"  - Узел: {comp['name']} (возраст: {comp['age_months']} мес)")

    print("\n=== 4. Проверка POST /api/equipment ===")
    new_eq = {
        "id": "boiler_tp240_01",
        "name": "Котел паровой барабанный ТП-240-1",
        "serial_number": "SN-TP240-2015-11",
        "location": "Котельный цех ТЭЦ",
        "installation_date": "2015-09-01",
        "component_age": "9 лет 2 месяца",
        "last_maintenance_date": "2026-05-18",
        "status": "operational",
        "components": [
            {
                "id": "screen_pipes_01",
                "name": "Фронтовой экран топочной камеры",
                "type": "Экранные трубы парогенератора",
                "installation_date": "2015-09-01",
                "age_months": 110,
                "criticality_factor": 1.9
            }
        ]
    }
    r = client.post("/api/equipment", json=new_eq)
    assert r.status_code == 201
    created_eq = r.json()
    print(f"Создан новый агрегат: {created_eq['id']} -> {created_eq['name']}")

    print("\n=== 5. Проверка POST /api/inspect (YOLO + Конвертер + LLM) ===")
    # Генерируем тестовое изображение с текстурой сварного шва / коррозии
    img = Image.new("RGB", (640, 640), color=(140, 140, 140))
    draw = ImageDraw.Draw(img)
    # Имитация ржавчины и сварного шва
    draw.rectangle([100, 100, 300, 250], fill=(160, 82, 45))
    draw.line([50, 400, 580, 420], fill=(50, 50, 50), width=18)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr.seek(0)

    files = {"file": ("test_pipe.jpg", img_byte_arr, "image/jpeg")}
    data = {"equipment_id": target_eq_id}

    r = client.post("/api/inspect", files=files, data=data)
    assert r.status_code == 200, f"Inspect failed: {r.text}"
    insp_res = r.json()
    print(f"Инспекция завершена:")
    print(f"  Оборудование: {insp_res['equipment_name']}")
    print(f"  Найдено дефектов: {insp_res['defects_count']}")
    print(f"  Критичность (LLM): {insp_res['expert_opinion']['criticality']}")
    print(f"  Причина (LLM): {insp_res['expert_opinion']['probable_cause'][:100]}...")
    print(f"  Количество рекомендаций: {len(insp_res['expert_opinion']['recommendations'])}")
    print(f"  Фото: {insp_res['image_url']}")
    if insp_res['annotated_image_url']:
        print(f"  Аннотированное фото: {insp_res['annotated_image_url']}")

    print("\n=== 6. Проверка POST /api/reports ===")
    report_data = {
        "equipment_id": target_eq_id,
        "repair_status": "in_progress",
        "dispatcher_notes": "Срочный вызов аварийной бригады ТОиР",
        "defects": insp_res["defects"],
        "expert_opinion": insp_res["expert_opinion"],
        "photo_url": insp_res["image_url"],
        "final_photo_url": insp_res.get("annotated_image_url")
    }
    r = client.post("/api/reports", json=report_data)
    assert r.status_code == 201, f"Report create failed: {r.text}"
    created_rep = r.json()
    print(f"Акт осмотра создан: {created_rep['id']}")
    print(f"  Статус: {created_rep['repair_status']}")
    print(f"  Дефектов в акте: {created_rep['defects_count']}")

    print("\n=== 7. Проверка GET /api/reports ===")
    r = client.get("/api/reports")
    assert r.status_code == 200
    reports = r.json()
    print(f"Журнал диспетчера содержит актов: {len(reports)}")
    assert len(reports) > 0

    print("\n Все тесты успешно пройдены! Пайплайн и API полностью функциональны.")

if __name__ == "__main__":
    test_full_pipeline()
