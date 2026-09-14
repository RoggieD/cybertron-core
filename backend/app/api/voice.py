import asyncio
import subprocess

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.core.config import get_settings


router = APIRouter(prefix="/api/voice", tags=["voice"])
settings = get_settings()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    voice: str | None = None


def _discover_kokoro_base_url_sync() -> tuple[str, str]:
    """Resolve Kokoro without depending on a Docker-assigned IP."""
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


def _whisper_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.whisper_api_key:
        headers["Authorization"] = f"Bearer {settings.whisper_api_key}"
    return headers


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


@router.get("/stt/status")
async def stt_status() -> dict:
    base_url = settings.whisper_base_url.rstrip("/")
    reachable = False
    authenticated = bool(settings.whisper_api_key)

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(
                f"{base_url.rsplit('/v1', 1)[0]}/docs",
                headers=_whisper_headers(),
                follow_redirects=True,
            )
        reachable = response.status_code < 500
    except httpx.HTTPError:
        reachable = False

    return {
        "provider": "faster-whisper",
        "base_url": base_url,
        "model": settings.whisper_model,
        "authenticated": authenticated,
        "reachable": reachable,
    }


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    if not settings.whisper_api_key:
        raise HTTPException(
            status_code=503,
            detail="Whisper API key is not configured.",
        )

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Audio upload is empty.")
    if len(audio) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio upload exceeds 25 MB.")

    files = {
        "file": (
            file.filename or "audio.webm",
            audio,
            file.content_type or "application/octet-stream",
        )
    }
    data = {"model": settings.whisper_model}

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.whisper_base_url.rstrip('/')}/audio/transcriptions",
                headers=_whisper_headers(),
                files=files,
                data=data,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500]
        raise HTTPException(
            status_code=502,
            detail=f"Whisper STT returned {exc.response.status_code}: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Whisper STT is unavailable: {exc}",
        ) from exc

    payload = response.json()
    text = str(payload.get("text", "")).strip()
    return {"text": text, "provider": "faster-whisper", "model": settings.whisper_model}


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
