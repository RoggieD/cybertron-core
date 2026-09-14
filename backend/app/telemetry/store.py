import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


DB_PATH = Path("data/cybertron.db")


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
            CREATE TABLE IF NOT EXISTS telemetry_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL,
                disk_percent REAL NOT NULL,
                gpu_percent REAL,
                gpu_memory_percent REAL,
                gpu_power_watts REAL,
                docker_running INTEGER NOT NULL,
                docker_total INTEGER NOT NULL,
                services_reachable INTEGER NOT NULL,
                services_total INTEGER NOT NULL,
                listeners INTEGER NOT NULL,
                service_latency_ms REAL NOT NULL
            )
            """
        )

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(telemetry_samples)"
            ).fetchall()
        }
        for column in (
            "gpu_percent",
            "gpu_memory_percent",
            "gpu_power_watts",
        ):
            if column not in columns:
                connection.execute(
                    f"ALTER TABLE telemetry_samples ADD COLUMN {column} REAL"
                )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_telemetry_samples_timestamp
            ON telemetry_samples(timestamp)
            """
        )


def insert_sample(sample: dict) -> None:
    initialize()

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO telemetry_samples (
                timestamp,
                cpu_percent,
                memory_percent,
                disk_percent,
                gpu_percent,
                gpu_memory_percent,
                gpu_power_watts,
                docker_running,
                docker_total,
                services_reachable,
                services_total,
                listeners,
                service_latency_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample["timestamp"],
                sample["cpu_percent"],
                sample["memory_percent"],
                sample["disk_percent"],
                sample.get("gpu_percent"),
                sample.get("gpu_memory_percent"),
                sample.get("gpu_power_watts"),
                sample["docker_running"],
                sample["docker_total"],
                sample["services_reachable"],
                sample["services_total"],
                sample["listeners"],
                sample["service_latency_ms"],
            ),
        )


def recent_samples(limit: int = 240) -> list[dict]:
    initialize()

    limit = max(1, min(limit, 10000))

    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT
                timestamp,
                cpu_percent,
                memory_percent,
                disk_percent,
                gpu_percent,
                gpu_memory_percent,
                gpu_power_watts,
                docker_running,
                docker_total,
                services_reachable,
                services_total,
                listeners,
                service_latency_ms
            FROM telemetry_samples
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        dict(row)
        for row in reversed(rows)
    ]


def prune(days: int = 7) -> None:
    initialize()

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=days)
    ).isoformat()

    with _connect() as connection:
        connection.execute(
            """
            DELETE FROM telemetry_samples
            WHERE timestamp < ?
            """,
            (cutoff,),
        )
