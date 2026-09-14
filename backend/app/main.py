from fastapi import FastAPI

from backend.app.api.chat import router as chat_router
from backend.app.api.health import router as health_router
from backend.app.api.models import router as models_router
from backend.app.api.traces import router as traces_router
from backend.app.api.websocket import router as websocket_router
from backend.app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.0.1",
    description="CyberTron Orchestration & Reasoning Engine",
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(models_router)
app.include_router(traces_router)
app.include_router(websocket_router)


@app.get("/")
async def root() -> dict:
    return {
        "service": settings.app_name,
        "status": "online",
        "api": "/api/health",
        "websocket": "/ws",
        "docs": "/docs",
    }
