from datetime import datetime, timezone

from fastapi import APIRouter

from backend.app.core.config import get_settings

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
