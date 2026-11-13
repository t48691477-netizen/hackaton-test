from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.defect import DefectItem

class CriticalityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class LLMRecommendation(BaseModel):
    criticality: CriticalityLevel = Field(
        ..., 
        description="Уровень критичности дефектов для безаварийной работы: low, medium, high",
        examples=[CriticalityLevel.HIGH]
    )
    probable_cause: str = Field(
        ..., 
        description="Предполагаемая физико-химическая или эксплуатационная причина возникновения дефектов",
        examples=["Кавитационная эрозия с последующим электрохимическим коррозионным поражением металла шва из-за нарушения регламента гидроиспытаний и отсутствия пассивации."]
    )
    recommendations: List[str] = Field(
        ..., 
        description="Пошаговая рекомендация по ТОиР: локализация, методы неразрушающего контроля, ремонт и регламент безопасности",
        examples=[
            "1. Немедленно снизить рабочее давление на агрегате на 30% и уведомить диспетчера цеха.",
            "2. Выполнить ультразвуковую дефектоскопию (УЗД) зоны сварного соединения на глубину трещины.",
            "3. Произвести механическую зачистку очага коррозии до чистого металла (степень Sa 2.5).",
            "4. Вырезать дефектный участок шва и выполнить повторную сварку электродами типа Э50А с контролем твердости.",
            "5. Нанести двухкомпонентное антикоррозионное полиуретановое покрытие толщиной не менее 180 мкм."
        ]
    )

class InspectResponse(BaseModel):
    equipment_id: str = Field(..., description="ID проинспектированного оборудования", examples=["pump_station_3"])
    equipment_name: str = Field(..., description="Наименование оборудования", examples=["Насос сетевой 1Д1250-125"])
    timestamp: str = Field(..., description="Метка времени инспекции", examples=["2026-11-13T10:15:30Z"])
    defects_count: int = Field(..., description="Количество выявленных дефектов", examples=[2])
    defects: List[DefectItem] = Field(..., description="Список дефектов с боксами, масками и уверенностью")
    expert_opinion: LLMRecommendation = Field(..., description="Заключение Главного эксперта ТОиР (LLM)")
    image_url: str = Field(..., description="URL сохраненного исходного фото", examples=["/static/uploads/insp_1731481234_orig.jpg"])
    annotated_image_url: Optional[str] = Field(None, description="URL размеченного изображения с визуализацией масок и боксов", examples=["/static/uploads/insp_1731481234_annotated.jpg"])
