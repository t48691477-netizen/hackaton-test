from typing import List, Optional
from fastapi import APIRouter, Query, status
from app.schemas.report import ReportCreate, ReportResponse, RepairStatus
from app.services.storage import storage_service

router = APIRouter(prefix="/api/reports", tags=["Reports & Dispatcher (Акты осмотра и диспетчеризация)"])

@router.get(
    "",
    response_model=List[ReportResponse],
    summary="Получить реестр актов осмотра для диспетчера",
    description="Возвращает журнал всех актов дефектоскопии и ремонтов. Поддерживает фильтрацию по статусу ремонта и ID оборудования."
)
def get_reports(
    repair_status: Optional[RepairStatus] = Query(None, description="Фильтр по статусу (pending, in_progress, completed, rejected)"),
    equipment_id: Optional[str] = Query(None, description="Фильтр по идентификатору оборудования")
):
    status_val = repair_status if isinstance(repair_status, RepairStatus) else None
    eq_val = equipment_id if isinstance(equipment_id, str) else None
    return storage_service.get_reports(repair_status=status_val, equipment_id=eq_val)

@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Сохранить акт осмотра, статус ремонта и итоговое фото",
    description="Регистрирует официальный акт осмотра ТОиР с перечнем дефектов, заключением LLM, статусом ремонта и фотоматериалами."
)
def create_report(report_in: ReportCreate):
    return storage_service.create_report(report_in)
