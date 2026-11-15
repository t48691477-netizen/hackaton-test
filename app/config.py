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
        "Включает детекцию дефектов единой YOLO-моделью (weights/defects_yolo.onnx) "
        "и генерацию экспертных заключений главного инженера ТОиР на базе LLM."
    )
    
    # Weights configuration
    WEIGHTS_DIR: Path = BASE_DIR / "weights"
    UNIFIED_LOCAL_PATH: Path = _first_existing(os.getenv("UNIFIED_WEIGHTS"), "defects_yolo.onnx")
    
    # Storage and uploads
    UPLOAD_DIR: Path = BASE_DIR / "static" / "uploads"
    DATA_DIR: Path = BASE_DIR / "data"
    # PostgreSQL DSN описаны в database/README.md; SQLite больше не используется.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_TASKS_URL: str = os.getenv("DATABASE_TASKS_URL", "") or os.getenv("DATABASE_URL", "")
    DATABASE_EMPLOYEES_URL: str = os.getenv("DATABASE_EMPLOYEES_URL", "") or os.getenv("DATABASE_URL", "")
    DATABASE_CREDENTIALS_URL: str = os.getenv("DATABASE_CREDENTIALS_URL", "") or os.getenv("DATABASE_URL", "")
    
    # LLM Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "")
    OLLAMA_TIMEOUT: float = float(os.getenv("OLLAMA_TIMEOUT", "90"))
    
    # Inference settings
    CONF_THRESHOLD: float = 0.25

settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
