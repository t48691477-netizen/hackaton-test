from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.routers._deps import storage_dep
from app.routers.auth import require_dispatch, require_scan
from app.schemas.report import ReportCreate, ReportResponse, ReportStatusUpdate, RepairStatus

router = APIRouter(prefix="/api/reports", tags=["Reports & Dispatcher (Акты осмотра и диспетчеризация)"])

@router.get(
    "",
    response_model=List[ReportResponse],
    summary="Получить реестр актов осмотра для диспетчера",
    description="Возвращает журнал всех актов дефектоскопии и ремонтов. Поддерживает фильтрацию по статусу ремонта и ID оборудования."
)
def get_reports(
    repair_status: Optional[RepairStatus] = Query(None, description="Фильтр по статусу (pending, in_progress, completed, rejected)"),
    equipment_id: Optional[str] = Query(None, description="Фильтр по идентификатору оборудования"),
    _account=Depends(require_dispatch),
    storage=Depends(storage_dep),
):
    status_val = repair_status if isinstance(repair_status, RepairStatus) else None
    eq_val = equipment_id if isinstance(equipment_id, str) else None
    return storage.get_reports(repair_status=status_val, equipment_id=eq_val)

@router.get(
    "/{report_id}", response_model=ReportResponse,
    summary="Получить акт осмотра по ID"
)
def get_report(report_id: str, _account=Depends(require_dispatch), storage=Depends(storage_dep)):
    report = storage.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report

@router.patch(
    "/{report_id}/status", response_model=ReportResponse,
    summary="Изменить статус задачи"
)
def update_report_status(
    report_id: str,
    update: ReportStatusUpdate,
    _account=Depends(require_dispatch),
    storage=Depends(storage_dep),
):
    try:
        report = storage.update_report_status(
            report_id, update.status, update.dispatcher_notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report

@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Сохранить акт осмотра, статус ремонта и итоговое фото",
    description="Регистрирует официальный акт осмотра ТОиР с перечнем дефектов, заключением LLM, статусом ремонта и фотоматериалами."
)
def create_report(report_in: ReportCreate, _account=Depends(require_scan), storage=Depends(storage_dep)):
    try:
        return storage.create_report(report_in)
    except ValueError as exc:
        from app.services.db import DatabaseError

        if isinstance(exc.__cause__, DatabaseError) or "не удалось" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Хранилище отчётов временно недоступно.",
            ) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
