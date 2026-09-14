from datetime import datetime, timedelta, timezone

from backend.app.telemetry.incidents import (
    incident_analytics,
    incidents_since,
    recent_incidents,
    search_incidents,
)


def _midnight_utc() -> datetime:
    now_local = datetime.now().astimezone()

    midnight_local = now_local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return midnight_local.astimezone(timezone.utc)


async def incident_summary(
    mode: str = "recent",
    hours: int | None = None,
    severity: str | None = None,
) -> dict:
    analytics = incident_analytics()

    if mode == "critical":
        incidents = search_incidents(
            severity="critical",
            limit=50,
        )

    elif mode in {
        "overnight",
        "today",
        "since_midnight",
    }:
        incidents = incidents_since(
            _midnight_utc(),
            severity=severity,
        )

    elif mode == "time_window":
        window_hours = max(
            1,
            min(hours or 1, 168),
        )

        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(hours=window_hours)
        )

        incidents = incidents_since(
            cutoff,
            severity=severity,
        )

    else:
        incidents = recent_incidents(
            limit=50
        )

    return {
        "mode": mode,
        "hours": hours,
        "severity_filter": severity,
        "analytics": analytics,
        "recent": incidents,
    }
