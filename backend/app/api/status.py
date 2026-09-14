from fastapi import APIRouter

from backend.app.tools.overview import system_overview


router = APIRouter(
    prefix="/api/status",
    tags=["status"],
)


@router.get("/overview")
async def status_overview() -> dict:
    return await system_overview()
