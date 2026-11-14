from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class DefectCategory(str, Enum):
    CORROSION = "corrosion"
    WELDING_DEFECT = "welding_defect"
    CRACK = "crack"
    UNKNOWN = "unknown"

class DefectItem(BaseModel):
    id: str = Field(
        ..., 
        description="Уникальный идентификатор обнаруженного дефекта",
        examples=["defect_1"]
    )
    label: str = Field(
        ..., 
        description="Наименование дефекта (Rust, Bad Weld, copper corrosion, etc.)",
        examples=["corrosion", "Bad Weld"]
    )
    category: DefectCategory = Field(
        ...,
        description="Категория дефекта: corrosion (коррозия) или welding_defect (сварной шов/трещина)",
        examples=[DefectCategory.CORROSION]
    )
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Уверенность модели в детекции от 0.0 до 1.0",
        examples=[0.92]
    )
    bbox: List[float] = Field(
        ..., 
        min_length=4, 
        max_length=4, 
        description="Координаты бокса в пикселях: [x_min, y_min, x_max, y_max]",
        examples=[[120.5, 84.0, 310.2, 450.8]]
    )
    bbox_normalized: List[float] = Field(
        ..., 
        min_length=4, 
        max_length=4, 
        description="Координаты бокса, нормализованные от 0.0 до 1.0: [x_min, y_min, x_max, y_max]",
        examples=[[0.12, 0.08, 0.31, 0.45]]
    )
    polygon: Optional[List[List[float]]] = Field(
        default=None,
        description="Массив точек [x, y] контура маски сегментации в нормализованных координатах [0.0 - 1.0]",
        examples=[[[0.12, 0.08], [0.15, 0.12], [0.22, 0.25], [0.31, 0.45], [0.12, 0.08]]]
    )
    model_source: str = Field(
        ..., 
        description="Название исходной нейросети",
        examples=["Decizez/yolov-corrosion-detection", "avinashhm/welding-defect-yolov8-full-training"]
    )

class DefectSummary(BaseModel):
    defect_type: str = Field(..., description="Тип дефекта", examples=["corrosion"])
    confidence: float = Field(..., description="Уверенность", examples=[0.89])
    model: str = Field(..., description="Модель детекции", examples=["Decizez/yolov-corrosion-detection"])
