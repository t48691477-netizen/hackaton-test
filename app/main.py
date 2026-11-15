import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.middleware import IngressRateLimitMiddleware
from app.routers import auth_router, detect_router, equipment_router, inspect_router, reports_router
from app.services.model_loader import model_loader

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Сервер ТОиР Эксперт AI запущен. UI на /.")
    model_loader.warm_up()
    from app.routers.front_compat import warm_up as _front_warm
    _front_warm()
    yield
    print("[Shutdown] Завершение работы сервиса.")

_docs_enabled = os.getenv("TOIR_DISABLE_DOCS", "false").lower() != "true"

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    lifespan=lifespan
)

# Same-origin clients need no CORS. Set an exact comma-separated origin list when browser clients are hosted elsewhere.
_cors_origins = [origin.strip() for origin in os.getenv("TOIR_CORS_ORIGINS", "").split(",") if origin.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Frame-Id"],
    )

app.add_middleware(
    IngressRateLimitMiddleware,
    limit=max(1, int(os.getenv("TOIR_INGRESS_RATE_LIMIT", "1200"))),
    window_seconds=max(1, int(os.getenv("TOIR_INGRESS_RATE_WINDOW_SECONDS", "60"))),
)

# Раздача статических файлов (загруженные и аннотированные фото)
app.mount("/static", StaticFiles(directory=str(settings.BASE_DIR / "static")), name="static")

# Подключение роутеров API
app.include_router(auth_router)
app.include_router(detect_router)
app.include_router(equipment_router)
app.include_router(inspect_router)
app.include_router(reports_router)
from app.routers.front_compat import router as front_compat_router
app.include_router(front_compat_router)

@app.get("/", tags=["UI"])
@app.get("/ui", tags=["UI"])
def serve_ui():
    index_file = settings.BASE_DIR / "static" / "index.html"
    return FileResponse(str(index_file))

@app.get("/api/info", tags=["Root"])
def service_info():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs" if _docs_enabled else None,
        "redoc_url": "/redoc" if _docs_enabled else None,
        "status": "online"
    }

@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "models": {
            "corrosion_segmentation": model_loader.corrosion_loaded,
            "welding_defect_detection": model_loader.welding_loaded
        }
    }
