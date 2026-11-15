import os
from pathlib import Path
from pydantic import BaseModel

os.environ["YOLO_OFFLINE"] = "true"
os.environ["ULTRALYTICS_OFFLINE"] = "true"

BASE_DIR = Path(__file__).resolve().parent.parent

def _first_existing(*names: str | None) -> Path:
    candidates = []
    for n in names:
        if not n:
            continue
        p = Path(n)
        candidates.append(p if p.is_absolute() else BASE_DIR / "weights" / n)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0] if candidates else BASE_DIR / "weights" / "missing.pt"


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
    CORROSION_LOCAL_PATH: Path = _first_existing(
        os.getenv("CORROSION_WEIGHTS"), "Basic_YOLO11_v1.pt", "corrosion_yolo26.pt", "corrosion_yolov11_seg.pt"
    )

    WELDING_MODEL_REPO: str = "avinashhm/welding-defect-yolov8-full-training"
    WELDING_MODEL_FILENAME: str = "best.pt"
    WELDING_LOCAL_PATH: Path = _first_existing(os.getenv("WELDING_WEIGHTS"), "welding_yolov8_det.pt")
    UNIFIED_LOCAL_PATH: Path = _first_existing(os.getenv("UNIFIED_WEIGHTS"), "best.pt", "defects_yolo.onnx")
    OIL_LOCAL_PATH: Path = _first_existing(os.getenv("OIL_WEIGHTS"), "oil_yolo26.pt", "oil_leaks.pt")
    
    # Storage and uploads
    UPLOAD_DIR: Path = BASE_DIR / "static" / "uploads"
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = BASE_DIR / "data" / "toir.db"
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "")
    OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "90"))
    
    # Inference settings
    CONF_THRESHOLD_CORROSION: float = 0.25
    CONF_THRESHOLD_WELDING: float = 0.25

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
