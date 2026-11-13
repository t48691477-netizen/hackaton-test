import os
from pathlib import Path
from pydantic import BaseModel

os.environ["YOLO_OFFLINE"] = "true"
os.environ["ULTRALYTICS_OFFLINE"] = "true"

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseModel):
    BASE_DIR: Path = BASE_DIR
    PROJECT_NAME: str = "ТОиР Эксперт AI API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "Интеллектуальная система предиктивной аналитики и детекции дефектов оборудования (ТОиР). "
        "Включает сегментацию очагов коррозии (YOLOv11-seg), детекцию дефектов сварных швов (YOLOv8-det) "
        "и генерацию экспертных заключений главного инженера ТОиР на базе LLM."
    )
    
    # Weights configuration
    WEIGHTS_DIR: Path = BASE_DIR / "weights"
    CORROSION_MODEL_REPO: str = "Decizez/yolov-corrosion-detection"
    CORROSION_MODEL_FILENAME: str = "Basic_YOLO11_v1.pt"
    CORROSION_LOCAL_PATH: Path = BASE_DIR / "weights" / "corrosion_yolov11_seg.pt"

    WELDING_MODEL_REPO: str = "avinashhm/welding-defect-yolov8-full-training"
    WELDING_MODEL_FILENAME: str = "best.pt"
    WELDING_LOCAL_PATH: Path = BASE_DIR / "weights" / "welding_yolov8_det.pt"
    
    # Storage and uploads
    UPLOAD_DIR: Path = BASE_DIR / "static" / "uploads"
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = BASE_DIR / "data" / "toir.db"
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    
    # Inference settings
    CONF_THRESHOLD_CORROSION: float = 0.25
    CONF_THRESHOLD_WELDING: float = 0.25

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
