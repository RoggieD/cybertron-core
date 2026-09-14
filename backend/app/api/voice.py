import asyncio
import subprocess

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


def _discover_kokoro_base_url_sync() -> tuple[str, str]:
    """Resolve Kokoro without depending on a Docker-assigned IP.

    Prefer an explicitly configured base URL when it is reachable. If it is not,
    inspect the named local container and build a URL from its current Docker IP.
    This keeps voice working across container restarts where the bridge address
    can change.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range.NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                settings.kokoro_container_name,
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=True,
        )
        addresses = [item.strip() for item in result.stdout.split() if item.strip()]
        if addresses:
            return (
                f"http://{addresses[0]}:{settings.kokoro_container_port}/v1",
                "docker-discovery",
            )
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return settings.kokoro_base_url.rstrip("/"), "configured"


async def _kokoro_base_url() -> tuple[str, str]:
    return await asyncio.to_thread(_discover_kokoro_base_url_sync)


@router.get("/status")
async def voice_status() -> dict:
    base_url, source = await _kokoro_base_url()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base_url}/models")
        reachable = response.status_code < 500
    except httpx.HTTPError:
        reachable = False

    return {
        "provider": "kokoro-fastapi",
        "base_url": base_url,
        "endpoint_source": source,
        "container": settings.kokoro_container_name,
        "default_voice": settings.kokoro_voice,
        "reachable": reachable,
    }


@router.post("/speech")
async def synthesize_speech(request: SpeechRequest) -> Response:
    base_url, _ = await _kokoro_base_url()
    payload = {
        "model": settings.kokoro_model,
        "input": request.text,
        "voice": request.voice or settings.kokoro_voice,
        "response_format": "mp3",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{base_url}/audio/speech",
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
