import asyncio
import json
import sqlite3
from pathlib import Path

from backend.app.events.schema import CoreEvent


class TraceStore:
    def __init__(
        self,
        database_path: str = "data/cybertron.db",
    ) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._lock = asyncio.Lock()
        self._initialize_sync()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "PRAGMA journal_mode=WAL"
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    trace_id TEXT,
                    parent_event_id TEXT,
                    actor_json TEXT,
                    target_json TEXT,
                    status TEXT,
                    metadata_json TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_trace_events_trace_id
                ON trace_events(trace_id)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_trace_events_timestamp
                ON trace_events(timestamp)
                """
            )

            connection.commit()

    async def initialize(self) -> None:
        await asyncio.to_thread(
            self._initialize_sync
        )

    def _save_sync(
        self,
        event: CoreEvent,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO trace_events (
                    event_id,
                    event_type,
                    timestamp,
                    session_id,
                    trace_id,
                    parent_event_id,
                    actor_json,
                    target_json,
                    status,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.timestamp.isoformat(),
                    event.session_id,
                    event.trace_id,
                    event.parent_event_id,
                    json.dumps(event.actor),
                    json.dumps(event.target),
                    event.status,
                    json.dumps(event.metadata),
                ),
            )
            connection.commit()

    async def save(
        self,
        event: CoreEvent,
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(
                self._save_sync,
                event,
            )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> dict:
        event = dict(row)
        event["actor"] = json.loads(event.pop("actor_json") or "null")
        event["target"] = json.loads(event.pop("target_json") or "null")
        event["metadata"] = json.loads(event.pop("metadata_json") or "{}")
        return event

    def _recent_sync(
        self,
        limit: int,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM trace_events
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [self._row_to_event(row) for row in rows]

    async def recent(
        self,
        limit: int = 50,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self._recent_sync,
            limit,
        )

    def _by_trace_sync(
        self,
        trace_id: str,
        limit: int,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM trace_events
                WHERE trace_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (trace_id, limit),
            ).fetchall()

        return [self._row_to_event(row) for row in rows]

    async def by_trace(
        self,
        trace_id: str,
        limit: int = 1000,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self._by_trace_sync,
            trace_id,
            limit,
        )

    def _recent_trace_summaries_sync(
        self,
        limit: int,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    trace_id,
                    MIN(timestamp) AS started_at,
                    MAX(timestamp) AS ended_at,
                    COUNT(*) AS event_count,
                    MAX(CASE WHEN event_type = 'response.generated' THEN 1 ELSE 0 END)
                        AS completed,
                    MAX(CASE WHEN event_type = 'model.error' THEN 1 ELSE 0 END)
                        AS errored
                FROM trace_events
                WHERE trace_id IS NOT NULL
                  AND trace_id != ''
                GROUP BY trace_id
                ORDER BY MAX(timestamp) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    async def recent_trace_summaries(
        self,
        limit: int = 25,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self._recent_trace_summaries_sync,
            limit,
        )


trace_store = TraceStore()
