from datetime import datetime, timedelta, timezone

from backend.app.telemetry.incidents import (
    incident_analytics,
    recent_incidents,
    search_incidents,
)


def _overnight_cutoff() -> datetime:
    now = datetime.now().astimezone()

    start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return start.astimezone(timezone.utc)


async def incident_summary(
    mode: str = "recent",
) -> dict:
    analytics = incident_analytics()

    if mode == "critical":
        incidents = search_incidents(
            severity="critical",
            limit=50,
        )

    elif mode == "overnight":
        cutoff = _overnight_cutoff()

        incidents = [
            item
            for item in recent_incidents(limit=200)
            if item.get("timestamp")
            and datetime.fromisoformat(
                item["timestamp"]
            ) >= cutoff
        ]

    else:
        incidents = recent_incidents(limit=50)

    return {
        "mode": mode,
        "analytics": analytics,
        "recent": incidents,
    }
