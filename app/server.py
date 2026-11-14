import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

from app.config import settings
from app.schemas.equipment import EquipmentCreate, EquipmentResponse
from app.schemas.report import ReportCreate, ReportResponse, RepairStatus
from app.schemas.inspection import InspectResponse
from app.services.storage import storage_service
from app.services.detector import defect_detector
from app.services.llm_expert import llm_expert_service

flask_app = Flask(
    __name__,
    static_folder=str(settings.BASE_DIR / "static"),
    static_url_path="/static"
)
CORS(flask_app)

# --- 1. UI и Документация ---

@flask_app.route("/")
@flask_app.route("/ui")
def serve_ui():
    index_path = settings.BASE_DIR / "static" / "index.html"
    return send_file(str(index_path))

@flask_app.route("/openapi.json")
def serve_openapi_spec():
    spec_path = settings.BASE_DIR / "openapi.json"
    if spec_path.exists():
        with open(spec_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({"error": "openapi.json not found"}), 404

@flask_app.route("/docs")
def swagger_ui():
    # Автономный Swagger UI через CDN/inline
    html = """<!DOCTYPE html>
<html>
<head>
  <title>ТОиР Эксперт AI — Swagger UI</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    body { margin: 0; background: #fafafa; }
    .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout"
      });
    };
  </script>
</body>
</html>"""
    return html

@flask_app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    })

# --- 2. Эндпоинты Оборудования (GET/POST /api/equipment) ---

@flask_app.route("/api/equipment", methods=["GET"])
def get_equipment_list():
    items = storage_service.get_all_equipment()
    return jsonify([it.model_dump() for it in items])

@flask_app.route("/api/equipment/<equipment_id>", methods=["GET"])
def get_equipment_detail(equipment_id):
    item = storage_service.get_equipment_by_id(equipment_id)
    if not item:
        return jsonify({"detail": f"Оборудование с ID '{equipment_id}' не найдено"}), 404
    return jsonify(item.model_dump())

@flask_app.route("/api/equipment", methods=["POST"])
def create_or_update_equipment():
    data = request.get_json(force=True)
    try:
        eq_in = EquipmentCreate.model_validate(data)
    except Exception as e:
        return jsonify({"detail": f"Ошибка валидации Pydantic: {e}"}), 422

    saved = storage_service.save_equipment(eq_in)
    return jsonify(saved.model_dump()), 201

# --- 3. Эндпоинт Инспекции (POST /api/inspect) ---

@flask_app.route("/api/inspect", methods=["POST"])
def inspect_equipment_endpoint():
    if "file" not in request.files:
        return jsonify({"detail": "Отсутствует обязательное поле 'file' в форме"}), 400

    file = request.files["file"]
    equipment_id = request.form.get("equipment_id", "default_equipment")

    suffix = Path(file.filename or "image.jpg").suffix.lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        return jsonify({"detail": "Недопустимый формат файла (.jpg, .jpeg, .png, .webp)"}), 400

    eq = storage_service.get_equipment_by_id(equipment_id)
    if eq:
        eq_name = eq.name
        comp_age = eq.component_age
        last_to = eq.last_maintenance_date
    else:
        eq_name = f"Промышленный агрегат (ID: {equipment_id})"
        comp_age = "5 лет (по умолчанию)"
        last_to = "2026-01-01"

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    saved_filename = f"insp_{timestamp_str}_orig{suffix}"
    saved_file_path = settings.UPLOAD_DIR / saved_filename
    file.save(str(saved_file_path))

    # Запуск YOLO + Конвертер
    try:
        defects, annotated_path = defect_detector.detect(saved_file_path)
    except Exception as e:
        return jsonify({"detail": f"Ошибка инференса YOLO: {e}"}), 500

    # Запуск эксперта ТОиР
    expert_opinion = llm_expert_service.analyze(
        equipment_name=eq_name,
        component_age=comp_age,
        last_maintenance_date=last_to,
        defects=defects
    )

    storage_service.increment_inspection_count(equipment_id)

    image_url = f"/static/uploads/{saved_filename}"
    annotated_url = f"/static/uploads/{annotated_path.name}" if annotated_path else None

    resp = InspectResponse(
        equipment_id=equipment_id,
        equipment_name=eq_name,
        timestamp=datetime.now().isoformat(),
        defects_count=len(defects),
        defects=defects,
        expert_opinion=expert_opinion,
        image_url=image_url,
        annotated_image_url=annotated_url
    )
    return jsonify(resp.model_dump())

# --- 4. Эндпоинты Актов (GET/POST /api/reports) ---

@flask_app.route("/api/reports", methods=["GET"])
def get_reports_endpoint():
    status_str = request.args.get("repair_status")
    equipment_id = request.args.get("equipment_id")
    repair_status = None
    if status_str:
        try:
            repair_status = RepairStatus(status_str)
        except ValueError:
            pass

    reports = storage_service.get_reports(repair_status=repair_status, equipment_id=equipment_id)
    return jsonify([r.model_dump() for r in reports])

@flask_app.route("/api/reports", methods=["POST"])
def create_report_endpoint():
    data = request.get_json(force=True)
    try:
        rep_in = ReportCreate.model_validate(data)
    except Exception as e:
        return jsonify({"detail": f"Ошибка валидации Pydantic: {e}"}), 422

    created = storage_service.create_report(rep_in)
    return jsonify(created.model_dump()), 201

if __name__ == "__main__":
    print(f">>> Сервер ТОиР Эксперт AI запущен на http://0.0.0.0:8000")
    print(f">>> UI панель: http://localhost:8000/")
    print(f">>> Swagger UI: http://localhost:8000/docs")
    flask_app.run(host="0.0.0.0", port=8000, threaded=True, debug=False)
