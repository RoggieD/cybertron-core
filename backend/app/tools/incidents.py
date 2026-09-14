from datetime import datetime, timedelta, timezone

from backend.app.telemetry.incidents import (
    incident_analytics,
    incidents_between,
    incidents_since,
    recent_incidents,
    search_incidents,
)


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _midnight_local() -> datetime:
    return _local_now().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _midnight_utc() -> datetime:
    return _midnight_local().astimezone(
        timezone.utc
    )


async def incident_summary(
    mode: str = "recent",
    hours: int | None = None,
    severity: str | None = None,
    hour: int | None = None,
    minute: int = 0,
) -> dict:
    analytics = incident_analytics()

    start = None
    end = None

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
        start = _midnight_utc()

        incidents = incidents_since(
            start,
            severity=severity,
        )

    elif mode == "time_window":
        window_hours = max(
            1,
            min(hours or 1, 168),
        )

        start = (
            datetime.now(timezone.utc)
            - timedelta(hours=window_hours)
        )

        incidents = incidents_since(
            start,
            severity=severity,
        )

    elif mode == "yesterday":
        today_local = _midnight_local()

        yesterday_local = (
            today_local
            - timedelta(days=1)
        )

        start = yesterday_local.astimezone(
            timezone.utc
        )

        end = today_local.astimezone(
            timezone.utc
        )

        incidents = incidents_between(
            start,
            end,
            severity=severity,
        )

    elif mode == "since_clock":
        now_local = _local_now()

        requested = now_local.replace(
            hour=max(0, min(hour or 0, 23)),
            minute=max(0, min(minute, 59)),
            second=0,
            microsecond=0,
        )

        # If the requested clock time is still ahead of us
        # today, interpret it as that time yesterday.
        if requested > now_local:
            requested -= timedelta(days=1)

        start = requested.astimezone(
            timezone.utc
        )

        incidents = incidents_since(
            start,
            severity=severity,
        )

    else:
        incidents = recent_incidents(
            limit=50
        )

    return {
        "mode": mode,
        "hours": hours,
        "hour": hour,
        "minute": minute,
        "severity_filter": severity,
        "window_start": (
            start.isoformat()
            if start
            else None
        ),
        "window_end": (
            end.isoformat()
            if end
            else None
        ),
        "analytics": analytics,
        "recent": incidents,
    }
