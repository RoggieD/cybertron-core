import asyncio
import json
import sqlite3
from pathlib import Path


PUBLIC_BIND_ADDRESSES = {
    "0.0.0.0",
    "::",
    "::0",
}


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
    def _listener_endpoint(listener: dict) -> str:
        return ":".join(
            [
                str(listener.get("address") or "?"),
                str(listener.get("port") or "?"),
            ]
        )

    @staticmethod
    def _listener_identity(listener: dict) -> str:
        return ":".join(
            [
                SecurityBaselineStore._listener_endpoint(listener),
                str(listener.get("process") or "unknown"),
            ]
        )

    @staticmethod
    def _process_signature(process: dict) -> str:
        return str(process.get("name") or "unknown")

    @staticmethod
    def _listener_map(snapshot: dict) -> dict[str, dict]:
        return {
            SecurityBaselineStore._listener_endpoint(item): item
            for item in snapshot.get("raw_evidence", {}).get("listeners", [])
        }

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
                "security_relevant_change": False,
                "new_listener_endpoints": [],
                "removed_listener_endpoints": [],
                "new_public_listener_endpoints": [],
                "removed_public_listener_endpoints": [],
                "listener_owner_changes": [],
                "new_process_names": [],
                "removed_process_names": [],
                "attention_score_delta": 0,
                "posture_changed": False,
            }

        previous_snapshot = previous["snapshot"]
        previous_listener_map = cls._listener_map(previous_snapshot)
        current_listener_map = cls._listener_map(current)

        previous_endpoints = set(previous_listener_map)
        current_endpoints = set(current_listener_map)

        new_endpoints = sorted(current_endpoints - previous_endpoints)
        removed_endpoints = sorted(previous_endpoints - current_endpoints)

        new_public_endpoints = [
            endpoint
            for endpoint in new_endpoints
            if current_listener_map[endpoint].get("address") in PUBLIC_BIND_ADDRESSES
        ]
        removed_public_endpoints = [
            endpoint
            for endpoint in removed_endpoints
            if previous_listener_map[endpoint].get("address") in PUBLIC_BIND_ADDRESSES
        ]

        owner_changes = []
        for endpoint in sorted(previous_endpoints & current_endpoints):
            previous_process = previous_listener_map[endpoint].get("process")
            current_process = current_listener_map[endpoint].get("process")
            if previous_process != current_process:
                owner_changes.append(
                    {
                        "endpoint": endpoint,
                        "previous_process": previous_process,
                        "current_process": current_process,
                    }
                )

        previous_processes = {
            cls._process_signature(item)
            for item in previous_snapshot.get("raw_evidence", {}).get("processes", [])
        }
        current_processes = {
            cls._process_signature(item)
            for item in current.get("raw_evidence", {}).get("processes", [])
        }

        new_process_names = sorted(current_processes - previous_processes)
        removed_process_names = sorted(previous_processes - current_processes)

        previous_score = int(previous_snapshot.get("attention_score") or 0)
        current_score = int(current.get("attention_score") or 0)
        posture_changed = previous_snapshot.get("posture") != current.get("posture")

        security_relevant_change = bool(
            new_endpoints
            or removed_endpoints
            or posture_changed
            or previous_score != current_score
        )

        return {
            "has_previous_baseline": True,
            "baseline_at": previous.get("generated_at"),
            "changed": bool(
                security_relevant_change
                or owner_changes
                or new_process_names
                or removed_process_names
            ),
            "security_relevant_change": security_relevant_change,
            "new_listener_endpoints": new_endpoints[:50],
            "removed_listener_endpoints": removed_endpoints[:50],
            "new_public_listener_endpoints": new_public_endpoints[:50],
            "removed_public_listener_endpoints": removed_public_endpoints[:50],
            "listener_owner_changes": owner_changes[:50],
            "new_process_names": new_process_names[:50],
            "removed_process_names": removed_process_names[:50],
            "attention_score_delta": current_score - previous_score,
            "posture_changed": posture_changed,
            "previous_posture": previous_snapshot.get("posture"),
            "current_posture": current.get("posture"),
            "context_only": {
                "process_churn": bool(new_process_names or removed_process_names),
                "owner_visibility_changed": bool(owner_changes),
            },
        }

    async def compare_and_record(self, snapshot: dict) -> dict:
        hostname = snapshot.get("evidence", {}).get("hostname")

        async with self._lock:
            previous = await asyncio.to_thread(self._latest_sync, hostname)
            comparison = self._compare(previous, snapshot)
            await asyncio.to_thread(self._save_sync, snapshot)

        return comparison


security_baseline_store = SecurityBaselineStore()
