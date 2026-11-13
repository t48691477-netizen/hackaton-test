import sys
import io
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, r"D:\hackaton_26")

from fastapi import UploadFile
from app.routers.equipment import get_equipment_list, get_equipment_detail, create_or_update_equipment
from app.routers.inspect import inspect_equipment
from app.routers.reports import create_report, get_reports
from app.schemas.equipment import EquipmentCreate, ComponentSchema
from app.schemas.report import ReportCreate, RepairStatus

async def main():
    print("--- 1. Тест Equipment API ---")
    eq_list = get_equipment_list()
    print(f"Список оборудования: {len(eq_list)} шт.")
    target_id = eq_list[0].id
    card = get_equipment_detail(target_id)
    print(f"Карточка: {card.name}, серийный номер: {card.serial_number}")
    print(f"Узлов в карточке: {len(card.components)}")

    print("\n--- 2. Тест Создания/Обновления оборудования ---")
    new_eq = EquipmentCreate(
        id="heat_exchanger_01",
        name="Теплообменник кожухотрубный ТК-800",
        serial_number="SN-TK-2022-771",
        location="Установка первичной переработки нефти ЭЛОУ-АВТ",
        installation_date="2022-03-10",
        component_age="4 года 8 месяцев",
        last_maintenance_date="2026-06-01",
        status="operational",
        components=[
            ComponentSchema(
                id="tube_bundle_01",
                name="Трубный пучок из коррозионностойкой стали",
                type="Теплообменный элемент",
                installation_date="2022-03-10",
                age_months=56,
                criticality_factor=1.7
            )
        ]
    )
    saved_eq = create_or_update_equipment(new_eq)
    print(f"Сохранен агрегат: {saved_eq.id} ({saved_eq.name})")

    print("\n--- 3. Тест Inspect API (YOLO Seg + Detect + LLM ТОиР) ---")
    # Создаем изображение с текстурой для инференса
    test_img = Image.new("RGB", (640, 640), color=(128, 128, 128))
    draw = ImageDraw.Draw(test_img)
    draw.ellipse([150, 150, 350, 300], fill=(180, 70, 30)) # Имитация ржавчины
    draw.rectangle([200, 420, 500, 440], fill=(40, 40, 40)) # Имитация шва
    buf = io.BytesIO()
    test_img.save(buf, format="JPEG")
    buf.seek(0)

    upload_file = UploadFile(
        file=buf,
        filename="test_joint_inspection.jpg",
        headers={"content-type": "image/jpeg"}
    )

    insp_result = await inspect_equipment(
        file=upload_file,
        equipment_id=target_id
    )

    print("Инспекция завершена успешно:")
    print(f"  Оборудование: {insp_result.equipment_name}")
    print(f"  Дефектов обнаружено: {insp_result.defects_count}")
    for d in insp_result.defects:
        print(f"    * [{d.category.value}] {d.label} (conf: {d.confidence:.2f})")
        print(f"      bbox [x_min, y_min, x_max, y_max]: {d.bbox}")
        print(f"      bbox_normalized: {d.bbox_normalized}")
        if d.polygon:
            print(f"      polygon points (normalized): {len(d.polygon)} точек, sample: {d.polygon[:2]}")

    print("\n--- 4. Экспертное заключение LLM ТОиР ---")
    print(f"  Критичность: {insp_result.expert_opinion.criticality.value}")
    print(f"  Причина: {insp_result.expert_opinion.probable_cause}")
    print("  Рекомендации пошагово:")
    for step in insp_result.expert_opinion.recommendations:
        print(f"    {step}")

    print("\n--- 5. Тест сохранения акта осмотра в Reports API ---")
    rep_create = ReportCreate(
        equipment_id=target_id,
        repair_status=RepairStatus.IN_PROGRESS,
        dispatcher_notes="Назначена бригада дефектоскопистов",
        defects=insp_result.defects,
        expert_opinion=insp_result.expert_opinion,
        photo_url=insp_result.image_url,
        final_photo_url=insp_result.annotated_image_url
    )
    saved_report = create_report(rep_create)
    print(f"Акт зарегистрирован: {saved_report.id}")
    print(f"  Оборудование: {saved_report.equipment_name}")
    print(f"  Статус ремонта: {saved_report.repair_status.value}")

    print("\n--- 6. Тест журнала актов диспетчера ---")
    all_reports = get_reports()
    print(f"Всего актов в реестре: {len(all_reports)}")
    assert len(all_reports) >= 1
    print(f"Последний акт: {all_reports[0].id}, статус: {all_reports[0].repair_status.value}")

    print("\n ВСЕ ЭТАПЫ ПАЙПЛАЙНА РАБОТАЮТ БЕЗУПРЕЧНО!")

if __name__ == "__main__":
    asyncio.run(main())
