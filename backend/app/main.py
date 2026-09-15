from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.chat import router as chat_router
from backend.app.api.health import router as health_router
from backend.app.api.knowledge import router as knowledge_router
from backend.app.api.models import router as models_router
from backend.app.api.traces import router as traces_router
from backend.app.api.status import router as status_router
from backend.app.api.websocket import router as websocket_router
from backend.app.api.memory import router as memory_router
from backend.app.api.security import router as security_router
from backend.app.api.voice import router as voice_router
from backend.app.api.agents import router as agents_router
from backend.app.core.config import get_settings
from backend.app.telemetry.sampler import (
    start_sampler,
    stop_sampler,
)
from backend.app.memory.middleware import ConversationMemoryMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.0.1",
    description="CyberTron Orchestration & Reasoning Engine",
)

app.add_middleware(ConversationMemoryMiddleware)

# The Vite development UI is served from a different origin/port than the
# FastAPI backend. Browser requests therefore require explicit CORS headers
# even when both services run on the same host. This development policy does
# not enable credentials and can be tightened to named origins for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(models_router)
app.include_router(traces_router)
app.include_router(status_router)
app.include_router(memory_router)
app.include_router(security_router)
app.include_router(voice_router)
app.include_router(agents_router)
app.include_router(websocket_router)


@app.on_event("startup")
async def telemetry_startup() -> None:
    await start_sampler()


@app.on_event("shutdown")
async def telemetry_shutdown() -> None:
    await stop_sampler()


@app.get("/")
async def root() -> dict:
    return {
        "service": settings.app_name,
        "status": "online",
        "api": "/api/health",
        "websocket": "/ws",
        "docs": "/docs",
    }

# C.O.R.E. Memory Approval API
