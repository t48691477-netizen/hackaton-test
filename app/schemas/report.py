from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.defect import DefectItem
from app.schemas.inspection import LLMRecommendation

class RepairStatus(str, Enum):
    PENDING = "pending"             # Ожидает назначения бригады
    IN_PROGRESS = "in_progress"     # В работе ТОиР
    COMPLETED = "completed"         # Ремонт завершен
    REJECTED = "rejected"           # Отклонено (ложное срабатывание)

class ReportCreate(BaseModel):
    equipment_id: str = Field(..., description="ID агрегата", examples=["pump_station_3"])
    repair_status: RepairStatus = Field(default=RepairStatus.PENDING, description="Статус ремонта", examples=[RepairStatus.PENDING])
    dispatcher_notes: Optional[str] = Field(default="", description="Комментарий диспетчера или инженера", examples=["Назначена аварийная бригада №2"])
    defects: List[DefectItem] = Field(default_factory=list, description="Список дефектов из акта осмотра")
    expert_opinion: LLMRecommendation = Field(..., description="Заключение и рекомендации эксперта")
    photo_url: str = Field(..., description="URL или путь к исходному/итоговому фото", examples=["/static/uploads/insp_1731481234_orig.jpg"])
    final_photo_url: Optional[str] = Field(None, description="URL итогового фото после выполнения ремонта")

class ReportResponse(BaseModel):
    id: str = Field(..., description="Уникальный номер акта осмотра", examples=["act_20261113_001"])
    equipment_id: str = Field(..., description="ID агрегата", examples=["pump_station_3"])
    equipment_name: str = Field(..., description="Наименование агрегата", examples=["Насос сетевой 1Д1250-125"])
    created_at: str = Field(..., description="Дата и время составления акта", examples=["2026-11-13T10:20:00Z"])
    repair_status: RepairStatus = Field(..., description="Текущий статус выполнения ремонта", examples=[RepairStatus.PENDING])
    dispatcher_notes: str = Field(default="", description="Заметки диспетчера")
    defects_count: int = Field(..., description="Количество зафиксированных дефектов", examples=[2])
    defects: List[DefectItem] = Field(..., description="Список дефектов")
    expert_opinion: LLMRecommendation = Field(..., description="Рекомендации эксперта ТОиР")
    photo_url: str = Field(..., description="URL исходного фото осмотра")
    final_photo_url: Optional[str] = Field(None, description="URL итогового фото после ремонта")
