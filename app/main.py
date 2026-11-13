import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import equipment_router, inspect_router, reports_router
from app.services.model_loader import model_loader

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Сервер ТОиР Эксперт AI запущен. Swagger доступен на /docs, UI на /.")
    yield
    print("[Shutdown] Завершение работы сервиса.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Разрешаем CORS для веб-панелей и мобильных клиентов
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Раздача статических файлов (загруженные и аннотированные фото)
app.mount("/static", StaticFiles(directory=str(settings.BASE_DIR / "static")), name="static")

# Подключение роутеров API
app.include_router(equipment_router)
app.include_router(inspect_router)
app.include_router(reports_router)

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
        "docs_url": "/docs",
        "redoc_url": "/redoc",
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
