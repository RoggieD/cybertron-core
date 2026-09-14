from backend.app.telemetry.incidents import (
    incident_analytics,
    recent_incidents,
)


async def incident_summary() -> dict:
    analytics = incident_analytics()
    incidents = recent_incidents(limit=20)

    return {
        "analytics": analytics,
        "recent": incidents,
    }
