from backend.app.telemetry.store import recent_samples
from fastapi import APIRouter

from backend.app.tools.overview import system_overview
from backend.app.tools.services import service_status


router = APIRouter(
    prefix="/api/status",
    tags=["status"],
)


@router.get("/overview")
async def status_overview() -> dict:
    return await system_overview()


@router.get("/services")
async def status_services() -> dict:
    return await service_status()


@router.get("/history")
async def status_history(
    limit: int = 240,
) -> dict:
    samples = recent_samples(limit)

    return {
        "count": len(samples),
        "samples": samples,
    }
