import asyncio
import json
import sqlite3
from pathlib import Path


class SecurityBaselineStore:
    def __init__(self, database_path: str = "data/cybertron.db") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._initialize_sync()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS security_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generated_at TEXT NOT NULL,
                    hostname TEXT,
                    snapshot_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_security_snapshots_generated_at
                ON security_snapshots(generated_at)
                """
            )
            connection.commit()

    @staticmethod
    def _listener_signature(listener: dict) -> str:
        return ":".join(
            [
                str(listener.get("address") or "?"),
                str(listener.get("port") or "?"),
                str(listener.get("process") or "unknown"),
            ]
        )

    @staticmethod
    def _process_signature(process: dict) -> str:
        return str(process.get("name") or "unknown")

    def _latest_sync(self, hostname: str | None) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT generated_at, snapshot_json
                FROM security_snapshots
                WHERE (? IS NULL OR hostname = ?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (hostname, hostname),
            ).fetchone()

        if row is None:
            return None

        return {
            "generated_at": row["generated_at"],
            "snapshot": json.loads(row["snapshot_json"]),
        }

    def _save_sync(self, snapshot: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO security_snapshots (
                    generated_at,
                    hostname,
                    snapshot_json
                ) VALUES (?, ?, ?)
                """,
                (
                    snapshot.get("generated_at"),
                    snapshot.get("evidence", {}).get("hostname"),
                    json.dumps(snapshot),
                ),
            )
            connection.commit()

    @classmethod
    def _compare(cls, previous: dict | None, current: dict) -> dict:
        if previous is None:
            return {
                "has_previous_baseline": False,
                "baseline_at": None,
                "changed": False,
                "new_listeners": [],
                "removed_listeners": [],
                "new_process_names": [],
                "removed_process_names": [],
                "attention_score_delta": 0,
                "posture_changed": False,
            }

        previous_snapshot = previous["snapshot"]

        previous_listeners = {
            cls._listener_signature(item)
            for item in previous_snapshot.get("raw_evidence", {}).get("listeners", [])
        }
        current_listeners = {
            cls._listener_signature(item)
            for item in current.get("raw_evidence", {}).get("listeners", [])
        }

        previous_processes = {
            cls._process_signature(item)
            for item in previous_snapshot.get("raw_evidence", {}).get("processes", [])
        }
        current_processes = {
            cls._process_signature(item)
            for item in current.get("raw_evidence", {}).get("processes", [])
        }

        new_listeners = sorted(current_listeners - previous_listeners)
        removed_listeners = sorted(previous_listeners - current_listeners)
        new_process_names = sorted(current_processes - previous_processes)
        removed_process_names = sorted(previous_processes - current_processes)

        previous_score = int(previous_snapshot.get("attention_score") or 0)
        current_score = int(current.get("attention_score") or 0)
        posture_changed = previous_snapshot.get("posture") != current.get("posture")

        return {
            "has_previous_baseline": True,
            "baseline_at": previous.get("generated_at"),
            "changed": bool(
                new_listeners
                or removed_listeners
                or new_process_names
                or removed_process_names
                or previous_score != current_score
                or posture_changed
            ),
            "new_listeners": new_listeners[:50],
            "removed_listeners": removed_listeners[:50],
            "new_process_names": new_process_names[:50],
            "removed_process_names": removed_process_names[:50],
            "attention_score_delta": current_score - previous_score,
            "posture_changed": posture_changed,
            "previous_posture": previous_snapshot.get("posture"),
            "current_posture": current.get("posture"),
        }

    async def compare_and_record(self, snapshot: dict) -> dict:
        hostname = snapshot.get("evidence", {}).get("hostname")

        async with self._lock:
            previous = await asyncio.to_thread(self._latest_sync, hostname)
            comparison = self._compare(previous, snapshot)
            await asyncio.to_thread(self._save_sync, snapshot)

        return comparison


security_baseline_store = SecurityBaselineStore()
