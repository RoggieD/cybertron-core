import asyncio
import re
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


def _extract_number(text: str, label: str) -> float | None:
    match = re.search(
        rf"\b{re.escape(label)}\s*:\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_integer(text: str, label: str) -> int | None:
    value = _extract_number(text, label)
    return int(value) if value is not None else None


def _system_overview_spoken_summary(text: str) -> str | None:
    upper = text.upper()
    if "SYSTEM OVERVIEW" not in upper and "SYSTEM STATUS" not in upper:
        return None

    host_match = re.search(r"\bHost(?:name)?\s*:\s*([^\s]+)", text, re.IGNORECASE)
    host = host_match.group(1) if host_match else "the host"

    cpu = _extract_number(text, "CPU usage")
    memory = _extract_number(text, "Memory usage")
    disk = _extract_number(text, "Disk usage")
    containers = _extract_integer(text, "Containers")
    running = _extract_integer(text, "Running")
    unreachable = _extract_integer(text, "Unreachable")

    healthy_match = re.search(
        r"\bHealthy\s*:\s*(\d+)\s*/\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    healthy = int(healthy_match.group(1)) if healthy_match else None
    service_total = int(healthy_match.group(2)) if healthy_match else None

    resource_warning = False
    resource_elevated = False

    if cpu is not None and cpu >= 90:
        resource_warning = True
    elif cpu is not None and cpu >= 75:
        resource_elevated = True

    if memory is not None and memory >= 90:
        resource_warning = True
    elif memory is not None and memory >= 80:
        resource_elevated = True

    if disk is not None and disk >= 95:
        resource_warning = True
    elif disk is not None and disk >= 85:
        resource_elevated = True

    service_warning = unreachable is not None and unreachable > 0

    if resource_warning:
        opening = f"{host} needs attention."
    elif resource_elevated or service_warning:
        opening = f"{host} is healthy overall, with one item needing attention."
    else:
        opening = f"{host} is healthy overall."

    resource_parts: list[str] = []
    if cpu is not None:
        resource_parts.append(f"CPU is {cpu:g} percent")
    if memory is not None:
        resource_parts.append(f"memory is {memory:g} percent")
    if disk is not None:
        resource_parts.append(f"disk usage is {disk:g} percent")

    sentences = [opening]

    if resource_parts:
        if not resource_warning and not resource_elevated:
            sentences.append(
                "System resource usage is comfortable: " + ", ".join(resource_parts) + "."
            )
        else:
            sentences.append("Current resource usage: " + ", ".join(resource_parts) + ".")

    if containers is not None and running is not None:
        sentences.append(f"{running} of {containers} containers are running.")

    if healthy is not None and service_total is not None:
        if unreachable:
            noun = "service is" if unreachable == 1 else "services are"
            sentences.append(
                f"{healthy} of {service_total} monitored services are healthy, and "
                f"{unreachable} {noun} unreachable."
            )
        else:
            sentences.append(f"All {service_total} monitored services are healthy.")

    if service_warning:
        sentences.append("The unreachable service is the only monitored issue needing attention.")
    elif resource_elevated:
        sentences.append("Resource usage is elevated but has not reached the warning threshold.")
    elif resource_warning:
        sentences.append("At least one resource has reached a warning threshold.")

    return " ".join(sentences)


def _prepare_spoken_text(text: str) -> str:
    """Create deterministic speech for known verified tool outputs."""
    system_summary = _system_overview_spoken_summary(text)
    if system_summary:
        return system_summary
    return text


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
        "language": settings.whisper_language,
        "prompt_configured": bool(settings.whisper_prompt.strip()),
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
    data = {
        "model": settings.whisper_model,
        "language": settings.whisper_language,
        "prompt": settings.whisper_prompt,
    }

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
    return {
        "text": text,
        "provider": "faster-whisper",
        "model": settings.whisper_model,
    }


@router.post("/speech")
async def synthesize_speech(request: SpeechRequest) -> Response:
    base_url, _ = await _kokoro_base_url()
    payload = {
        "model": settings.kokoro_model,
        "input": _prepare_spoken_text(request.text),
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
