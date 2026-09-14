from backend.app.telemetry.store import recent_samples
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


@router.get("/history")
async def status_history(
    limit: int = 240,
) -> dict:
    samples = recent_samples(limit)

    return {
        "count": len(samples),
        "samples": samples,
    }


@router.get("/incidents")
async def status_incidents(
    limit: int = 50,
    severity: str | None = None,
    state: str | None = None,
) -> dict:
    from backend.app.telemetry.incidents import (
        acknowledged_incident_ids,
        active_incident_ids,
        recent_incidents,
    )

    incidents = recent_incidents(
        limit=limit,
        severity=severity,
        state=state,
    )

    return {
        "active": active_incident_ids(),
        "acknowledged": acknowledged_incident_ids(),
        "count": len(incidents),
        "filters": {
            "severity": severity,
            "state": state,
        },
        "incidents": incidents,
    }


@router.post("/incidents/{incident_id}/acknowledge")
async def acknowledge_status_incident(
    incident_id: str,
) -> dict:
    from backend.app.telemetry.incidents import (
        acknowledge_incident,
    )

    return acknowledge_incident(incident_id)
