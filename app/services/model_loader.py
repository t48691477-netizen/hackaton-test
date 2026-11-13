import logging
from pathlib import Path
from typing import Optional
from ultralytics import YOLO
from huggingface_hub import hf_hub_download
from app.config import settings

logger = logging.getLogger("toir_models")
logging.basicConfig(level=logging.INFO)

class ModelLoader:
    _instance: Optional["ModelLoader"] = None

    def __init__(self):
        self.corrosion_model: Optional[YOLO] = None
        self.welding_model: Optional[YOLO] = None
        self.corrosion_loaded: bool = False
        self.welding_loaded: bool = False

    @classmethod
    def get_instance(cls) -> "ModelLoader":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _resolve_model_path(self, local_path: Path, repo_id: str, filename: str) -> Optional[str]:
        # 1. Проверяем локальный файл весов
        if local_path.exists():
            logger.info(f"Используем локальные веса: {local_path}")
            return str(local_path)

        # 2. Пытаемся скачать с Hugging Face Hub
        logger.info(f"Локальные веса не найдены по пути {local_path}. Загрузка из Hugging Face: {repo_id}/{filename}...")
        try:
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=str(settings.WEIGHTS_DIR),
                local_dir_use_symlinks=False
            )
            logger.info(f"Веса успешно загружены: {downloaded_path}")
            return downloaded_path
        except Exception as e:
            logger.warning(f"Не удалось скачать веса с Hugging Face ({repo_id}): {e}")
            return None

    def load_corrosion_model(self) -> Optional[YOLO]:
        if self.corrosion_model is not None:
            return self.corrosion_model

        path = self._resolve_model_path(
            local_path=settings.CORROSION_LOCAL_PATH,
            repo_id=settings.CORROSION_MODEL_REPO,
            filename=settings.CORROSION_MODEL_FILENAME
        )

        if path:
            try:
                logger.info(f"Инициализация модели сегментации коррозии из {path}...")
                self.corrosion_model = YOLO(path)
                self.corrosion_loaded = True
                logger.info("Модель сегментации коррозии готова к работе.")
            except Exception as e:
                logger.error(f"Ошибка загрузки весов модели коррозии: {e}")
        return self.corrosion_model

    def load_welding_model(self) -> Optional[YOLO]:
        if self.welding_model is not None:
            return self.welding_model

        path = self._resolve_model_path(
            local_path=settings.WELDING_LOCAL_PATH,
            repo_id=settings.WELDING_MODEL_REPO,
            filename=settings.WELDING_MODEL_FILENAME
        )

        if path:
            try:
                logger.info(f"Инициализация модели детекции дефектов сварных швов из {path}...")
                self.welding_model = YOLO(path)
                self.welding_loaded = True
                logger.info("Модель детекции сварных швов готова к работе.")
            except Exception as e:
                logger.error(f"Ошибка загрузки весов модели сварных швов: {e}")
        return self.welding_model

    def warm_up(self):
        """Предварительная загрузка обеих моделей при старте сервиса."""
        self.load_corrosion_model()
        self.load_welding_model()

model_loader = ModelLoader.get_instance()
