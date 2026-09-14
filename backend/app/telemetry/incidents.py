from datetime import datetime, timezone
from collections import deque
from threading import Lock


_incidents = deque(maxlen=200)
_lock = Lock()
_active_ids: set[str] = set()


def update_incidents(
    alerts: list[dict],
) -> None:
    global _active_ids

    current_ids = {
        alert["id"]
        for alert in alerts
    }

    with _lock:
        for alert in alerts:
            if alert["id"] not in _active_ids:
                event = dict(alert)
                event["state"] = "opened"
                _incidents.append(event)

        resolved = (
            _active_ids - current_ids
        )

        for alert_id in resolved:
            _incidents.append(
                {
                    "id": alert_id,
                    "severity": "info",
                    "title": "Incident Resolved",
                    "message": (
                        f"{alert_id} returned "
                        "to normal."
                    ),
                    "state": "resolved",
                    "timestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            )

        _active_ids = current_ids


def recent_incidents(
    limit: int = 50,
) -> list[dict]:
    limit = max(1, min(limit, 200))

    with _lock:
        return list(_incidents)[-limit:]


def active_incident_ids() -> list[str]:
    with _lock:
        return sorted(_active_ids)
