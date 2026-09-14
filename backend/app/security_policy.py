import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.app.security_baseline import PUBLIC_BIND_ADDRESSES


class SecurityPolicyStore:
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
                CREATE TABLE IF NOT EXISTS security_approved_public_listeners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hostname TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    address TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    approved_at TEXT NOT NULL,
                    approved_by TEXT NOT NULL DEFAULT 'local-admin',
                    source TEXT NOT NULL DEFAULT 'administrator-approved',
                    UNIQUE(hostname, endpoint)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_security_approved_public_listeners_host
                ON security_approved_public_listeners(hostname)
                """
            )
            connection.commit()

    @staticmethod
    def _endpoint(listener: dict) -> str:
        return f"{listener.get('address') or '?'}:{listener.get('port') or '?'}"

    @staticmethod
    def _display_endpoint(endpoint: str) -> str:
        """Format IPv6 endpoints for human-readable/API presentation.

        Stored endpoint keys intentionally remain unchanged so existing learned
        and approved policy rows continue to compare against listener snapshots.
        """
        if endpoint.startswith("["):
            return endpoint
        address, separator, port = endpoint.rpartition(":")
        if not separator:
            return endpoint
        if ":" in address:
            return f"[{address}]:{port}"
        return endpoint

    @classmethod
    def _display_endpoints(cls, endpoints) -> list[str]:
        return [cls._display_endpoint(endpoint) for endpoint in sorted(endpoints)]

    def _approved_rows_sync(self, hostname: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT endpoint, address, port, approved_at, approved_by, source
                FROM security_approved_public_listeners
                WHERE hostname = ?
                ORDER BY port, address
                """,
                (hostname,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _learned_rows_sync(self, hostname: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT endpoint, address, port, first_observed_at, source
                FROM security_expected_public_listeners
                WHERE hostname = ?
                ORDER BY port, address
                """,
                (hostname,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _replace_with_learned_sync(self, hostname: str, approved_by: str) -> list[dict]:
        learned = self._learned_rows_sync(hostname)
        if not learned:
            return []

        approved_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM security_approved_public_listeners WHERE hostname = ?",
                (hostname,),
            )
            for row in learned:
                connection.execute(
                    """
                    INSERT INTO security_approved_public_listeners (
                        hostname,
                        endpoint,
                        address,
                        port,
                        approved_at,
                        approved_by,
                        source
                    ) VALUES (?, ?, ?, ?, ?, ?, 'administrator-approved')
                    """,
                    (
                        hostname,
                        row["endpoint"],
                        row["address"],
                        row["port"],
                        approved_at,
                        approved_by,
                    ),
                )
            connection.commit()
        return self._approved_rows_sync(hostname)

    async def status(self, hostname: str) -> dict:
        approved, learned = await asyncio.gather(
            asyncio.to_thread(self._approved_rows_sync, hostname),
            asyncio.to_thread(self._learned_rows_sync, hostname),
        )
        return {
            "hostname": hostname,
            "mode": "administrator-approved" if approved else "learned-baseline",
            "approved_configured": bool(approved),
            "approved_count": len(approved),
            "approved_endpoints": self._display_endpoints(
                row["endpoint"] for row in approved
            ),
            "learned_count": len(learned),
            "learned_endpoints": self._display_endpoints(
                row["endpoint"] for row in learned
            ),
        }

    async def approve_learned(self, hostname: str, approved_by: str = "local-admin") -> dict:
        async with self._lock:
            approved = await asyncio.to_thread(
                self._replace_with_learned_sync,
                hostname,
                approved_by,
            )
        if not approved:
            raise ValueError(
                f"No learned public-listener baseline exists for host {hostname}."
            )
        return await self.status(hostname)

    async def evaluate(self, hostname: str | None, listeners: list[dict]) -> dict:
        if not hostname:
            return {
                "mode": "unavailable",
                "approved_configured": False,
                "unexpected_public_listener_endpoints": [],
                "missing_approved_public_listener_endpoints": [],
            }

        approved = await asyncio.to_thread(self._approved_rows_sync, hostname)
        current_public = {
            self._endpoint(listener)
            for listener in listeners
            if listener.get("address") in PUBLIC_BIND_ADDRESSES
        }

        if not approved:
            return {
                "hostname": hostname,
                "mode": "learned-baseline",
                "approved_configured": False,
                "approved_public_listener_count": 0,
                "current_public_listener_count": len(current_public),
                "unexpected_public_listener_endpoints": [],
                "missing_approved_public_listener_endpoints": [],
                "note": (
                    "No administrator-approved listener policy exists yet. "
                    "Current exposure is still evaluated against the learned baseline."
                ),
            }

        approved_endpoints = {row["endpoint"] for row in approved}
        unexpected = current_public - approved_endpoints
        missing = approved_endpoints - current_public
        return {
            "hostname": hostname,
            "mode": "administrator-approved",
            "approved_configured": True,
            "approved_public_listener_count": len(approved_endpoints),
            "current_public_listener_count": len(current_public),
            "approved_public_listener_endpoints": self._display_endpoints(
                approved_endpoints
            ),
            "unexpected_public_listener_endpoints": self._display_endpoints(unexpected),
            "missing_approved_public_listener_endpoints": self._display_endpoints(missing),
            "note": (
                "This policy was explicitly approved by an administrator and is "
                "authoritative for public-listener drift detection."
            ),
        }


security_policy_store = SecurityPolicyStore()
