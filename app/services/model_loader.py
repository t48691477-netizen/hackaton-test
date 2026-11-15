import logging
from typing import Optional

from ultralytics import YOLO

from app.config import settings

logger = logging.getLogger("toir_models")
logging.basicConfig(level=logging.INFO)

class ModelLoader:
    _instance: Optional["ModelLoader"] = None

    def __init__(self):
        self.unified_model: Optional[YOLO] = None
        self.unified_loaded: bool = False

    @classmethod
    def get_instance(cls) -> "ModelLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_unified_model(self) -> Optional[YOLO]:
        """Загружает единую ONNX-модель детекции дефектов (weights/defects_yolo.onnx)."""
        if self.unified_model is not None:
            return self.unified_model

        path = settings.UNIFIED_LOCAL_PATH
        if not path.exists():
            logger.warning(f"Файл единой ONNX-модели не найден: {path}")
            return None

        try:
            logger.info(f"Инициализация единой ONNX-модели детекции дефектов из {path}...")
            self.unified_model = YOLO(str(path), task="detect")
            self.unified_loaded = True
            logger.info("Единая модель детекции дефектов готова к работе.")
        except Exception as e:
            logger.error(f"Ошибка загрузки единой ONNX-модели: {e}")
        return self.unified_model

    def warm_up(self):
        """Предварительная загрузка единой модели при старте сервиса."""
        self.load_unified_model()

model_loader = ModelLoader.get_instance()
