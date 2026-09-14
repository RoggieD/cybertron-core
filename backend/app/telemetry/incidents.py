import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


DB_PATH = Path("data/cybertron.db")
_lock = Lock()
_active_ids: set[str] = set()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")

    return connection


def initialize() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL,
                threshold REAL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_timestamp
            ON incidents(timestamp)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_incidents_incident_id
            ON incidents(incident_id)
            """
        )


def _insert_event(event: dict) -> None:
    initialize()

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO incidents (
                incident_id,
                severity,
                title,
                message,
                state,
                timestamp,
                value,
                threshold
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                event.get("severity", "info"),
                event.get("title", "Incident"),
                event.get("message", ""),
                event.get("state", "opened"),
                event.get(
                    "timestamp",
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
                ),
                event.get("value"),
                event.get("threshold"),
            ),
        )


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
                _insert_event(event)

        resolved = _active_ids - current_ids

        for alert_id in resolved:
            _insert_event(
                {
                    "id": alert_id,
                    "severity": "info",
                    "title": "Incident Resolved",
                    "message": (
                        f"{alert_id} returned to normal."
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
    severity: str | None = None,
    state: str | None = None,
) -> list[dict]:
    initialize()

    limit = max(1, min(limit, 500))

    query = """
        SELECT
            id,
            incident_id,
            severity,
            title,
            message,
            state,
            timestamp,
            value,
            threshold
        FROM incidents
    """

    clauses = []
    params: list = []

    if severity:
        clauses.append("severity = ?")
        params.append(severity.lower())

    if state:
        clauses.append("state = ?")
        params.append(state.lower())

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with _connect() as connection:
        rows = connection.execute(
            query,
            tuple(params),
        ).fetchall()

        events = [
            {
                "id": row["incident_id"],
                "severity": row["severity"],
                "title": row["title"],
                "message": row["message"],
                "state": row["state"],
                "timestamp": row["timestamp"],
                "value": row["value"],
                "threshold": row["threshold"],
            }
            for row in reversed(rows)
        ]

        # Add duration to resolved incidents by locating
        # the nearest preceding opened event.
        for event in events:
            if event["state"] != "resolved":
                continue

            opened = connection.execute(
                """
                SELECT timestamp
                FROM incidents
                WHERE incident_id = ?
                  AND state = 'opened'
                  AND timestamp <= ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    event["id"],
                    event["timestamp"],
                ),
            ).fetchone()

            if opened:
                try:
                    opened_at = datetime.fromisoformat(
                        opened["timestamp"]
                    )

                    resolved_at = datetime.fromisoformat(
                        event["timestamp"]
                    )

                    event["duration_seconds"] = round(
                        (
                            resolved_at - opened_at
                        ).total_seconds(),
                        2,
                    )
                except ValueError:
                    event["duration_seconds"] = None

    return events


def active_incident_ids() -> list[str]:
    with _lock:
        return sorted(_active_ids)


def acknowledge_incident(
    incident_id: str,
) -> dict:
    initialize()

    with _lock:
        if incident_id not in _active_ids:
            return {
                "ok": False,
                "reason": "incident_not_active",
                "incident_id": incident_id,
            }

    with _connect() as connection:
        latest = connection.execute(
            """
            SELECT state
            FROM incidents
            WHERE incident_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()

    if latest and latest["state"] == "acknowledged":
        return {
            "ok": True,
            "already_acknowledged": True,
            "incident_id": incident_id,
        }

    event = {
        "id": incident_id,
        "severity": "info",
        "title": "Incident Acknowledged",
        "message": (
            f"{incident_id} acknowledged by operator."
        ),
        "state": "acknowledged",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    _insert_event(event)

    return {
        "ok": True,
        "already_acknowledged": False,
        "incident_id": incident_id,
    }


def acknowledged_incident_ids() -> list[str]:
    initialize()

    with _lock:
        active = list(_active_ids)

    acknowledged = []

    with _connect() as connection:
        for incident_id in active:
            latest = connection.execute(
                """
                SELECT state
                FROM incidents
                WHERE incident_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (incident_id,),
            ).fetchone()

            if (
                latest
                and latest["state"] == "acknowledged"
            ):
                acknowledged.append(incident_id)

    return sorted(acknowledged)
