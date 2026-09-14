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
