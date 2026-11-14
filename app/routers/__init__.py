from app.routers.auth import router as auth_router
from app.routers.detect import router as detect_router
from app.routers.equipment import router as equipment_router
from app.routers.inspect import router as inspect_router
from app.routers.reports import router as reports_router

__all__ = ["auth_router", "detect_router", "equipment_router", "inspect_router", "reports_router"]
