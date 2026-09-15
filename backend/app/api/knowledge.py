import asyncio

from fastapi import APIRouter

from backend.app.knowledge.health import knowledge_health

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/status")
async def status() -> dict:
    return await asyncio.to_thread(knowledge_health)
