import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings


router = APIRouter(prefix="/api/voice", tags=["voice"])
settings = get_settings()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str | None = None


@router.get("/status")
async def voice_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{settings.kokoro_base_url}/models")
        reachable = response.status_code < 500
    except httpx.HTTPError:
        reachable = False

    return {
        "provider": "kokoro-fastapi",
        "base_url": settings.kokoro_base_url,
        "default_voice": settings.kokoro_voice,
        "reachable": reachable,
    }


@router.post("/speech")
async def synthesize_speech(request: SpeechRequest) -> Response:
    payload = {
        "model": settings.kokoro_model,
        "input": request.text,
        "voice": request.voice or settings.kokoro_voice,
        "response_format": "mp3",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{settings.kokoro_base_url}/audio/speech",
                json=payload,
                headers={"Authorization": "Bearer not-needed"},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Kokoro TTS returned {exc.response.status_code}: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Kokoro TTS is unavailable: {exc}",
        ) from exc

    media_type = response.headers.get("content-type", "audio/mpeg")
    return Response(content=response.content, media_type=media_type)
