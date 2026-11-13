import shutil
import time
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.config import settings
from app.schemas.inspection import InspectResponse
from app.services.storage import storage_service
from app.services.detector import defect_detector
from app.services.llm_expert import llm_expert_service

router = APIRouter(prefix="/api/inspect", tags=["Inspection & AI (Нейросети + LLM)"])

@router.post(
    "",
    response_model=InspectResponse,
    status_code=status.HTTP_200_OK,
    summary="Комплексная инспекция: YOLO (детекция + сегментация) + Эксперт ТОиР (LLM)",
    description=(
        "Принимает фотографию узла оборудования и его ID. "
        "В едином пайплайне выполняет:\n"
        "1. Сегментацию очагов коррозии (Decizez/yolov-corrosion-detection) с получением полигонов;\n"
        "2. Детекцию дефектов сварных швов и трещин (avinashhm/welding-defect-yolov8-full-training) с получением боксов;\n"
        "3. Инженерный анализ Главным экспертом ТОиР (LLM) с расчетом критичности и пошаговыми рекомендациями;\n"
        "4. Отрисовку и сохранение аннотированного фото для веб/мобайла."
    )
)
async def inspect_equipment(
    file: UploadFile = File(..., description="Файл изображения (.jpg, .png, .webp) для детекции дефектов"),
    equipment_id: str = Form(..., description="ID оборудования в системе ТОиР", examples=["pump_d1250_03"])
):
    # Проверка расширения файла
    suffix = Path(file.filename or "image.jpg").suffix.lower()
    if suffix not in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимый формат файла. Поддерживаются: .jpg, .jpeg, .png, .webp, .bmp"
        )

    # Получаем данные об оборудовании из реестра
    equipment = storage_service.get_equipment_by_id(equipment_id)
    if equipment:
        equipment_name = equipment.name
        component_age = equipment.component_age
        last_maintenance_date = equipment.last_maintenance_date
    else:
        # Если оборудования нет, используем безопасный контекст
        equipment_name = f"Промышленный агрегат (ID: {equipment_id})"
        component_age = "5 лет (по умолчанию)"
        last_maintenance_date = "2026-01-01"

    # Сохраняем загруженный файл
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    saved_filename = f"insp_{timestamp_str}_orig{suffix}"
    saved_file_path = settings.UPLOAD_DIR / saved_filename

    try:
        with open(saved_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось сохранить загруженный файл: {e}"
        )

    # 1. Запуск детекции и сегментации YOLO
    try:
        defects, annotated_path = defect_detector.detect(saved_file_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка инференса нейросетей YOLO: {e}"
        )

    # 2. Вызов LLM Эксперта ТОиР
    expert_opinion = llm_expert_service.analyze(
        equipment_name=equipment_name,
        component_age=component_age,
        last_maintenance_date=last_maintenance_date,
        defects=defects
    )

    # Увеличиваем счетчик инспекций
    storage_service.increment_inspection_count(equipment_id)

    # Формируем публичные относительные URL к фото
    image_url = f"/static/uploads/{saved_filename}"
    annotated_url = f"/static/uploads/{annotated_path.name}" if annotated_path else None

    return InspectResponse(
        equipment_id=equipment_id,
        equipment_name=equipment_name,
        timestamp=datetime.now().isoformat(),
        defects_count=len(defects),
        defects=defects,
        expert_opinion=expert_opinion,
        image_url=image_url,
        annotated_image_url=annotated_url
    )
