from typing import Any

from app.config import settings
from app.schemas.defect import DefectItem
from app.services.model_loader import model_loader
from app.services.yolo_converter import YOLOOutputConverter


class ModelsUnavailableError(RuntimeError):
    pass


class LiveDetectorService:
    def __init__(self, loader: Any = model_loader, converter: Any = None):
        self.loader = loader
        self.converter = converter or YOLOOutputConverter()

    def detect(self, image_bgr: Any, conf: float, imgsz: int) -> tuple[list[DefectItem], dict[str, bool]]:
        model = self.loader.load_unified_model()
        loaded = {"unified": model is not None}
        if model is None:
            raise ModelsUnavailableError("No YOLO model is available")

        results = model.predict(source=image_bgr, conf=conf, imgsz=imgsz, device="cpu", verbose=False)
        defects = self.converter.convert_results(
            results=results,
            source_model=settings.UNIFIED_LOCAL_PATH.stem,
            conf_threshold=conf,
            start_id=1,
        )
        return defects, loaded
