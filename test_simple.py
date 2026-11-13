import sys
import io
import os
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, r"D:\hackaton_26")

from app.services.detector import defect_detector
from app.services.llm_expert import llm_expert_service
from app.services.storage import storage_service
from app.schemas.report import ReportCreate, RepairStatus

def run():
    print(">>> 1. Проверка реестра оборудования в БД SQLite:")
    items = storage_service.get_all_equipment()
    print(f"Найдено оборудования в БД: {len(items)}")
    for it in items:
        print(f"  * [{it.id}] {it.name} (узлов: {len(it.components)})")
    sys.stdout.flush()

    print("\n>>> 2. Тестирование ансамбля моделей YOLO (Corrosion + Welding):")
    # Создаем тестовое изображение с дефектом
    test_img = Image.new("RGB", (640, 640), color=(110, 110, 110))
    draw = ImageDraw.Draw(test_img)
    # Зона коррозии
    draw.ellipse([120, 120, 360, 320], fill=(160, 70, 20))
    # Линия сварного шва
    draw.rectangle([100, 450, 540, 480], fill=(30, 30, 30))
    test_path = Path(r"D:\hackaton_26\static\uploads\sample_test.jpg")
    test_img.save(test_path, format="JPEG")

    defects, annotated_path = defect_detector.detect(test_path)
    print(f"Инференс моделей завершен! Найдено дефектов: {len(defects)}")
    for d in defects:
        print(f"  - Дефект: {d.label} | Категория: {d.category} | Уверенность: {d.confidence:.2f}")
        print(f"    Бокс: {d.bbox}")
        print(f"    Нормализованный бокс [x_min, y_min, x_max, y_max]: {d.bbox_normalized}")
        if d.polygon:
            print(f"    Полигон маски (точек: {len(d.polygon)}): {d.polygon[:2]}...")
    if annotated_path:
        print(f"  Аннотированное изображение сохранено: {annotated_path}")
    sys.stdout.flush()

    print("\n>>> 3. Тестирование эксперта ТОиР (LLM):")
    target_eq = items[0]
    opinion = llm_expert_service.analyze(
        equipment_name=target_eq.name,
        component_age=target_eq.component_age,
        last_maintenance_date=target_eq.last_maintenance_date,
        defects=defects
    )
    print(f"Критичность: {opinion.criticality.value}")
    print(f"Причина: {opinion.probable_cause}")
    print("Рекомендации:")
    for r in opinion.recommendations:
        print(f"  * {r}")
    sys.stdout.flush()

    print("\n>>> 4. Тестирование создания и чтения актов осмотра:")
    rep = storage_service.create_report(ReportCreate(
        equipment_id=target_eq.id,
        repair_status=RepairStatus.IN_PROGRESS,
        dispatcher_notes="Акт сформирован по результатам автоматической инспекции",
        defects=defects,
        expert_opinion=opinion,
        photo_url=f"/static/uploads/{test_path.name}",
        final_photo_url=f"/static/uploads/{annotated_path.name}" if annotated_path else None
    ))
    print(f"Создан акт: {rep.id} для '{rep.equipment_name}'")
    reports = storage_service.get_reports()
    print(f"Всего актов в базе: {len(reports)}")
    sys.stdout.flush()
    print("\n>>> ПРОВЕРКА ПРОЙДЕНА УСПЕШНО! <<<")

if __name__ == "__main__":
    run()
