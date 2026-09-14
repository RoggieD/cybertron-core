from __future__ import annotations

import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.memory.policy import MemoryPolicy
from backend.app.memory.store import MemoryStore


class MemoryWriteOrchestrator:
    """
    Controlled persistent-memory write path.

    Agents/models never directly call MemoryStore.add().
    Proposed writes pass through MemoryPolicy first.

    Outcomes:
      committed - policy allowed automatic persistence
      pending   - explicit confirmation is required
      rejected  - policy denied the request
    """

    def __init__(
        self,
        db_path: str | Path = "data/cybertron.db",
    ) -> None:
        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.store = MemoryStore(
            self.db_path
        )

        self.policy = MemoryPolicy(
            self.db_path
        )

        self.initialize()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                    memory_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        status TEXT NOT NULL,
                        actor_type TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT NOT NULL DEFAULT '[]',
                        source TEXT,
                        policy_decision_id TEXT,
                        policy_reason TEXT,
                        memory_id TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        decided_by_type TEXT,
                        decided_by_id TEXT,
                        decided_at TEXT
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_proposals_status
                    ON memory_proposals(status);

                CREATE INDEX IF NOT EXISTS
                    idx_memory_proposals_actor
                    ON memory_proposals(
                        actor_type,
                        actor_id
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_proposals_created
                    ON memory_proposals(created_at);

                CREATE TABLE IF NOT EXISTS
                    memory_proposal_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        proposal_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        actor_type TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        detail TEXT,
                        timestamp TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_proposal_audit_id
                    ON memory_proposal_audit(
                        proposal_id
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_proposal_audit_time
                    ON memory_proposal_audit(
                        timestamp
                    );
                """
            )

    def _audit(
        self,
        connection: sqlite3.Connection,
        *,
        proposal_id: str,
        action: str,
        actor_type: str,
        actor_id: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_proposal_audit (
                proposal_id,
                action,
                actor_type,
                actor_id,
                detail,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                action,
                actor_type,
                actor_id,
                json.dumps(
                    detail or {},
                    sort_keys=True,
                ),
                self._utc_now(),
            ),
        )

    @staticmethod
    def _normalize_tags(
        tags: list[str] | None,
    ) -> list[str]:
        return sorted(
            {
                tag.strip().lower()
                for tag in (tags or [])
                if tag.strip()
            }
        )

    @staticmethod
    def _row_to_proposal(
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        return {
            "proposal_id":
                row["proposal_id"],
            "status":
                row["status"],
            "actor_type":
                row["actor_type"],
            "actor_id":
                row["actor_id"],
            "namespace":
                row["namespace"],
            "scope":
                row["scope"],
            "kind":
                row["kind"],
            "content":
                row["content"],
            "tags":
                json.loads(
                    row["tags"] or "[]"
                ),
            "source":
                row["source"],
            "policy_decision_id":
                row["policy_decision_id"],
            "policy_reason":
                row["policy_reason"],
            "memory_id":
                row["memory_id"],
            "created_at":
                row["created_at"],
            "updated_at":
                row["updated_at"],
            "decided_by_type":
                row["decided_by_type"],
            "decided_by_id":
                row["decided_by_id"],
            "decided_at":
                row["decided_at"],
        }

    def get(
        self,
        proposal_id: str,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM memory_proposals
                WHERE proposal_id = ?
                """,
                (
                    proposal_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_proposal(
            row
        )

    def propose(
        self,
        *,
        actor_type: str,
        actor_id: str,
        namespace: str,
        scope: str,
        kind: str,
        content: str,
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        content = content.strip()

        if not content:
            raise ValueError(
                "content is required"
            )

        normalized_tags = (
            self._normalize_tags(tags)
        )

        decision = self.policy.evaluate(
            operation="create",
            actor_type=actor_type,
            actor_id=actor_id,
            namespace=namespace,
            scope=scope,
            kind=kind,
            source=source,
            confirmed=False,
        )

        if decision.allowed:
            status = "committed"
        elif decision.requires_confirmation:
            status = "pending"
        else:
            status = "rejected"

        proposal_id = str(
            uuid.uuid4()
        )

        timestamp = self._utc_now()

        memory_id = None

        if status == "committed":
            memory = self.store.add(
                namespace=namespace,
                scope=scope,
                kind=kind,
                content=content,
                tags=normalized_tags,
                source=source,
                actor=(
                    f"{actor_type}:"
                    f"{actor_id}"
                ),
            )

            memory_id = memory["id"]

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_proposals (
                    proposal_id,
                    status,
                    actor_type,
                    actor_id,
                    namespace,
                    scope,
                    kind,
                    content,
                    tags,
                    source,
                    policy_decision_id,
                    policy_reason,
                    memory_id,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    proposal_id,
                    status,
                    actor_type,
                    actor_id,
                    namespace,
                    scope,
                    kind,
                    content,
                    json.dumps(
                        normalized_tags
                    ),
                    source,
                    decision.decision_id,
                    decision.reason,
                    memory_id,
                    timestamp,
                    timestamp,
                ),
            )

            self._audit(
                connection,
                proposal_id=proposal_id,
                action="proposed",
                actor_type=actor_type,
                actor_id=actor_id,
                detail={
                    "policy_allowed":
                        decision.allowed,
                    "requires_confirmation":
                        decision.requires_confirmation,
                    "policy_decision_id":
                        decision.decision_id,
                },
            )

            self._audit(
                connection,
                proposal_id=proposal_id,
                action=status,
                actor_type="system",
                actor_id="memory-orchestrator",
                detail={
                    "memory_id":
                        memory_id,
                    "reason":
                        decision.reason,
                },
            )

        result = self.get(
            proposal_id
        )

        if result is None:
            raise RuntimeError(
                "Proposal creation failed"
            )

        return result

    def decide(
        self,
        proposal_id: str,
        *,
        approved: bool,
        actor_type: str,
        actor_id: str,
    ) -> dict[str, Any]:
        proposal = self.get(
            proposal_id
        )

        if proposal is None:
            raise KeyError(
                "Memory proposal not found: "
                f"{proposal_id}"
            )

        if proposal["status"] != "pending":
            raise ValueError(
                "Only pending proposals may "
                "be approved or rejected."
            )

        if actor_type not in {
            "user",
            "system",
        }:
            raise PermissionError(
                "Only trusted user/system "
                "principals may decide "
                "memory proposals."
            )

        timestamp = self._utc_now()

        if not approved:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE memory_proposals
                    SET status = 'rejected',
                        updated_at = ?,
                        decided_by_type = ?,
                        decided_by_id = ?,
                        decided_at = ?
                    WHERE proposal_id = ?
                      AND status = 'pending'
                    """,
                    (
                        timestamp,
                        actor_type,
                        actor_id,
                        timestamp,
                        proposal_id,
                    ),
                )

                self._audit(
                    connection,
                    proposal_id=proposal_id,
                    action="rejected",
                    actor_type=actor_type,
                    actor_id=actor_id,
                    detail={
                        "decision":
                            "explicit-rejection"
                    },
                )

            result = self.get(
                proposal_id
            )

            if result is None:
                raise RuntimeError(
                    "Proposal rejection failed"
                )

            return result

        decision = self.policy.evaluate(
            operation="create",
            actor_type=proposal[
                "actor_type"
            ],
            actor_id=proposal[
                "actor_id"
            ],
            namespace=proposal[
                "namespace"
            ],
            scope=proposal[
                "scope"
            ],
            kind=proposal[
                "kind"
            ],
            source=proposal[
                "source"
            ],
            confirmed=True,
        )

        if not decision.allowed:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE memory_proposals
                    SET status = 'rejected',
                        policy_decision_id = ?,
                        policy_reason = ?,
                        updated_at = ?,
                        decided_by_type = ?,
                        decided_by_id = ?,
                        decided_at = ?
                    WHERE proposal_id = ?
                      AND status = 'pending'
                    """,
                    (
                        decision.decision_id,
                        decision.reason,
                        timestamp,
                        actor_type,
                        actor_id,
                        timestamp,
                        proposal_id,
                    ),
                )

                self._audit(
                    connection,
                    proposal_id=proposal_id,
                    action="rejected",
                    actor_type=actor_type,
                    actor_id=actor_id,
                    detail={
                        "decision":
                            "policy-rejected-after-confirmation",
                        "policy_decision_id":
                            decision.decision_id,
                        "reason":
                            decision.reason,
                    },
                )

            result = self.get(
                proposal_id
            )

            if result is None:
                raise RuntimeError(
                    "Proposal policy rejection failed"
                )

            return result

        memory = self.store.add(
            namespace=proposal[
                "namespace"
            ],
            scope=proposal[
                "scope"
            ],
            kind=proposal[
                "kind"
            ],
            content=proposal[
                "content"
            ],
            tags=proposal[
                "tags"
            ],
            source=proposal[
                "source"
            ],
            actor=(
                f"{actor_type}:"
                f"{actor_id}"
            ),
        )

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE memory_proposals
                SET status = 'committed',
                    memory_id = ?,
                    policy_decision_id = ?,
                    policy_reason = ?,
                    updated_at = ?,
                    decided_by_type = ?,
                    decided_by_id = ?,
                    decided_at = ?
                WHERE proposal_id = ?
                  AND status = 'pending'
                """,
                (
                    memory["id"],
                    decision.decision_id,
                    decision.reason,
                    timestamp,
                    actor_type,
                    actor_id,
                    timestamp,
                    proposal_id,
                ),
            )

            self._audit(
                connection,
                proposal_id=proposal_id,
                action="approved",
                actor_type=actor_type,
                actor_id=actor_id,
                detail={
                    "policy_decision_id":
                        decision.decision_id,
                },
            )

            self._audit(
                connection,
                proposal_id=proposal_id,
                action="committed",
                actor_type="system",
                actor_id="memory-orchestrator",
                detail={
                    "memory_id":
                        memory["id"]
                },
            )

        result = self.get(
            proposal_id
        )

        if result is None:
            raise RuntimeError(
                "Proposal commit failed"
            )

        return result

    def list_proposals(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT *
            FROM memory_proposals
            WHERE 1 = 1
        """

        params: list[Any] = []

        if status:
            normalized_status = (
                status.strip().lower()
            )

            if normalized_status not in {
                "pending",
                "committed",
                "rejected",
            }:
                raise ValueError(
                    "Invalid proposal status: "
                    f"{status}"
                )

            sql += """
                AND status = ?
            """

            params.append(
                normalized_status
            )

        sql += """
            ORDER BY created_at DESC
            LIMIT ?
        """

        params.append(
            max(
                1,
                min(limit, 500),
            )
        )

        with self._connect() as connection:
            rows = connection.execute(
                sql,
                tuple(params),
            ).fetchall()

        return [
            self._row_to_proposal(row)
            for row in rows
        ]

    def audit_history(
        self,
        proposal_id: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    proposal_id,
                    action,
                    actor_type,
                    actor_id,
                    detail,
                    timestamp
                FROM memory_proposal_audit
                WHERE proposal_id = ?
                ORDER BY id ASC
                """,
                (
                    proposal_id,
                ),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "proposal_id":
                    row["proposal_id"],
                "action":
                    row["action"],
                "actor_type":
                    row["actor_type"],
                "actor_id":
                    row["actor_id"],
                "detail":
                    json.loads(
                        row["detail"] or "{}"
                    ),
                "timestamp":
                    row["timestamp"],
            }
            for row in rows
        ]
