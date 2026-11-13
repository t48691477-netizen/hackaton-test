from app.routers.equipment import router as equipment_router
from app.routers.inspect import router as inspect_router
from app.routers.reports import router as reports_router

__all__ = ["equipment_router", "inspect_router", "reports_router"]
