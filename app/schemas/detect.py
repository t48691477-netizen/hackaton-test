from pydantic import BaseModel, Field

from app.schemas.defect import DefectCategory


class FastDefectItem(BaseModel):
    id: str
    label: str
    category: DefectCategory
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_normalized: list[float] = Field(min_length=4, max_length=4)
    polygon: list[list[float]] | None = None


class ModelLoadedStatus(BaseModel):
    corrosion: bool = False
    welding: bool = False


class DetectResponse(BaseModel):
    defects: list[FastDefectItem]
    frame_id: int | None
    inference_ms: float = Field(ge=0.0)
    model_loaded: ModelLoadedStatus
