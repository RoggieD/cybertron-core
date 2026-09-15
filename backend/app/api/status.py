import csv
import io
from backend.app.telemetry.store import recent_samples
from fastapi import APIRouter
from fastapi.responses import Response

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

@router.get("/incidents/search")
async def status_incident_search(
    q: str = "",
    severity: str | None = None,
    state: str | None = None,
    limit: int = 200,
) -> dict:
    from backend.app.telemetry.incidents import (
        search_incidents,
    )

    incidents = search_incidents(
        query=q,
        severity=severity,
        state=state,
        limit=limit,
    )

    return {
        "query": q,
        "count": len(incidents),
        "incidents": incidents,
    }


@router.get("/incidents/export")
async def status_incident_export(
    q: str = "",
    severity: str | None = None,
    state: str | None = None,
) -> Response:
    from backend.app.telemetry.incidents import (
        search_incidents,
    )

    incidents = search_incidents(
        query=q,
        severity=severity,
        state=state,
        limit=1000,
    )

    output = io.StringIO()

    writer = csv.DictWriter(
        output,
        extrasaction="ignore",
        fieldnames=[
            "id",
            "severity",
            "title",
            "message",
            "state",
            "timestamp",
            "value",
            "threshold",
        ],
    )

    writer.writeheader()
    writer.writerows(incidents)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                'attachment; filename="cybertron-incidents.csv"'
        },
    )



@router.get("/incidents/analytics")
async def status_incident_analytics() -> dict:
    from backend.app.telemetry.incidents import (
        incident_analytics,
    )

    return incident_analytics()


# Literal collection routes must precede the incident-ID route.
@router.get("/incidents/{incident_id}")
async def status_incident_detail(
    incident_id: str,
) -> dict:
    from backend.app.telemetry.incidents import (
        incident_timeline,
    )

    return incident_timeline(incident_id)



@router.get("/infrastructure")
async def status_infrastructure() -> dict:
    from backend.app.services.infrastructure import infrastructure_snapshot
    return await infrastructure_snapshot()
