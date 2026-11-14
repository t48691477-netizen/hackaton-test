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
        models = (
            ("corrosion", self.loader.load_corrosion_model(), settings.CORROSION_MODEL_REPO),
            ("welding", self.loader.load_welding_model(), settings.WELDING_MODEL_REPO),
        )
        loaded = {name: model is not None for name, model, _ in models}
        if not any(loaded.values()):
            raise ModelsUnavailableError("No YOLO model is available")

        defects: list[DefectItem] = []
        for name, model, source in models:
            if model is not None:
                results = model.predict(source=image_bgr, conf=conf, imgsz=imgsz, verbose=False)
                defects.extend(
                    self.converter.convert_results(
                        results=results,
                        source_model=source,
                        conf_threshold=conf,
                        start_id=len(defects) + 1,
                    )
                )
        return defects, loaded
