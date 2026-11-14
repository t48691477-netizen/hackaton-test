from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.routers.auth import require_scan, require_users
from app.schemas.equipment import EquipmentCreate, EquipmentResponse
from app.services.storage import storage_service

router = APIRouter(prefix="/api/equipment", tags=["Equipment (Оборудование и узлы)"])

@router.get(
    "",
    response_model=List[EquipmentResponse],
    summary="Получить список всего оборудования",
    description="Возвращает полный реестр агрегатов предприятия со статусами и счетчиком проверок."
)
def get_equipment_list(_account=Depends(require_scan)):
    return storage_service.get_all_equipment()

@router.get(
    "/{equipment_id}",
    response_model=EquipmentResponse,
    summary="Получить детальную карточку агрегата",
    description="Возвращает подробную карточку конкретного агрегата с узлами, датами ТО и коэффициентами критичности."
)
def get_equipment_detail(equipment_id: str, _account=Depends(require_scan)):
    item = storage_service.get_equipment_by_id(equipment_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Оборудование с ID '{equipment_id}' не найдено"
        )
    return item

@router.post(
    "",
    response_model=EquipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать или обновить агрегат (для веб-интерфейса)",
    description="Создает новую запись об агрегате или обновляет существующую, если передан существующий ID."
)
def create_or_update_equipment(equipment_in: EquipmentCreate, _account=Depends(require_users)):
    return storage_service.save_equipment(equipment_in)
