from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.providers.ollama import OllamaProvider
from backend.app.services.model_service import model_service

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelSelectionRequest(BaseModel):
    model: str


@router.get("")
async def list_models() -> dict:
    provider = OllamaProvider()

    try:
        models = await provider.list_models()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama unavailable: {exc}",
        ) from exc

    return {
        "provider": "ollama",
        "count": len(models),
        "models": models,
    }


@router.get("/health")
async def model_provider_health() -> dict:
    provider = OllamaProvider()
    healthy = await provider.health()

    return {
        "provider": "ollama",
        "status": "online" if healthy else "offline",
    }


@router.get("/state")
async def model_state() -> dict:
    try:
        return await model_service.get_state()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to read model state: {exc}",
        ) from exc


@router.post("/active")
async def set_active_model(
    request: ModelSelectionRequest,
) -> dict:
    try:
        return await model_service.set_active_model(
            request.model
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to change active model: {exc}",
        ) from exc
