from typing import List, Optional
from pydantic import BaseModel, Field

class ComponentSchema(BaseModel):
    id: str = Field(..., description="ID узла агрегата", examples=["comp_rotor_01"])
    name: str = Field(..., description="Наименование узла агрегата", examples=["Ротор турбины"])
    type: str = Field(..., description="Тип узла", examples=["Вращающийся механизм"])
    installation_date: str = Field(..., description="Дата монтажа узла (ГГГГ-ММ-ДД)", examples=["2021-04-12"])
    age_months: int = Field(..., ge=0, description="Возраст узла в месяцах", examples=[66])
    criticality_factor: float = Field(default=1.0, description="Коэффициент ответственности узла (0.5 - 2.0)", examples=[1.5])

class EquipmentBase(BaseModel):
    name: str = Field(..., description="Наименование оборудования", examples=["Насос сетевой центробежный 1Д1250-125"])
    serial_number: str = Field(..., description="Заводской серийный номер", examples=["SN-2019-9482-B"])
    location: str = Field(..., description="Цех / Участок / Место установки", examples=["Цех №3, насосная станция оборотного водоснабжения"])
    installation_date: str = Field(..., description="Дата ввода в эксплуатацию (ГГГГ-ММ-ДД)", examples=["2019-06-15"])
    component_age: str = Field(..., description="Возраст агрегата/узлов (текст или число лет)", examples=["7 лет 5 месяцев"])
    last_maintenance_date: str = Field(..., description="Дата последнего ТО (ГГГГ-ММ-ДД)", examples=["2026-03-20"])
    status: str = Field(default="operational", description="Текущий статус (operational, warning, maintenance, stopped)", examples=["operational"])
    components: List[ComponentSchema] = Field(default_factory=list, description="Список входящих узлов агрегата")

class EquipmentCreate(EquipmentBase):
    id: Optional[str] = Field(None, description="Опциональный ID агрегата (если передан, используется для обновления)", examples=["pump_station_3"])

class EquipmentResponse(EquipmentBase):
    id: str = Field(..., description="Уникальный идентификатор оборудования", examples=["pump_station_3"])
    created_at: str = Field(..., description="Дата и время создания записи", examples=["2026-11-01T10:00:00"])
    updated_at: str = Field(..., description="Дата и время последнего обновления", examples=["2026-11-13T09:30:00"])
    inspection_count: int = Field(default=0, description="Количество проведенных инспекций", examples=[4])
