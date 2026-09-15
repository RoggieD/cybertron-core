from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EpisodicStore:
    """Durable operational episodes derived from C.O.R.E. activity.

    Episodes summarize what happened; trace_events remain the detailed evidence.
    """

    def __init__(self, db_path: str | Path = "data/cybertron.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    trace_id TEXT,
                    agent_id TEXT,
                    tool_id TEXT,
                    prompt TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    status TEXT NOT NULL,
                    importance INTEGER NOT NULL DEFAULT 5,
                    pain_score INTEGER NOT NULL DEFAULT 5,
                    recurrence_count INTEGER NOT NULL DEFAULT 1,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_episodes_timestamp ON episodes(timestamp);
                CREATE INDEX IF NOT EXISTS idx_episodes_trace ON episodes(trace_id);
                CREATE INDEX IF NOT EXISTS idx_episodes_tool ON episodes(tool_id);
                CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
                """
            )

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["tags"] = json.loads(value.pop("tags_json") or "[]")
        value["metadata"] = json.loads(value.pop("metadata_json") or "{}")
        return value

    def record(
        self,
        *,
        prompt: str,
        outcome: str,
        status: str,
        session_id: str | None = None,
        trace_id: str | None = None,
        agent_id: str | None = None,
        tool_id: str | None = None,
        importance: int = 5,
        pain_score: int = 5,
        recurrence_count: int = 1,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        prompt = prompt.strip()
        outcome = outcome.strip()
        status = status.strip().lower()
        if not prompt or not outcome or not status:
            raise ValueError("prompt, outcome, and status are required")

        episode_id = str(uuid.uuid4())
        created = timestamp or datetime.now(timezone.utc).isoformat()
        normalized_tags = sorted({str(tag).strip().lower() for tag in (tags or []) if str(tag).strip()})
        metadata_value = dict(metadata or {})

        with self._connect() as connection:
            # Consecutive identical operational outcomes consolidate into one
            # durable episode while trace_events preserve every occurrence.
            previous = connection.execute(
                """
                SELECT * FROM episodes
                WHERE tool_id IS ? AND agent_id IS ? AND status = ? AND outcome = ?
                ORDER BY timestamp DESC LIMIT 1
                """,
                (tool_id, agent_id, status, outcome),
            ).fetchone()
            if previous is not None:
                previous_metadata = json.loads(previous["metadata_json"] or "{}")
                previous_metadata["previous_trace_id"] = previous["trace_id"]
                previous_metadata.update(metadata_value)
                connection.execute(
                    """
                    UPDATE episodes
                    SET timestamp = ?, session_id = ?, trace_id = ?,
                        recurrence_count = recurrence_count + 1,
                        importance = ?, pain_score = ?, tags_json = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        created, session_id, trace_id,
                        max(int(previous["importance"]), max(0, min(10, int(importance)))),
                        max(int(previous["pain_score"]), max(0, min(10, int(pain_score)))),
                        json.dumps(normalized_tags), json.dumps(previous_metadata, sort_keys=True),
                        previous["id"],
                    ),
                )
                return self.get(previous["id"]) or {}

            connection.execute(
                """
                INSERT INTO episodes (
                    id, timestamp, session_id, trace_id, agent_id, tool_id,
                    prompt, outcome, status, importance, pain_score,
                    recurrence_count, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id, created, session_id, trace_id, agent_id, tool_id,
                    prompt, outcome, status,
                    max(0, min(10, int(importance))), max(0, min(10, int(pain_score))),
                    max(1, int(recurrence_count)), json.dumps(normalized_tags),
                    json.dumps(metadata_value, sort_keys=True),
                ),
            )

        return self.get(episode_id) or {}

    def get(self, episode_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        return self._row(row) if row else None

    def recent(self, limit: int = 25) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 250))
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [self._row(row) for row in rows]


episodic_store = EpisodicStore()
