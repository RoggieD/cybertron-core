from __future__ import annotations

import json
import sqlite3
import uuid

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_KINDS = {
    "fact",
    "preference",
    "decision",
    "observation",
    "summary",
}


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class MemoryStore:
    """
    Persistent C.O.R.E. memory storage.

    Storage is deterministic and model-independent.
    All mutations are recorded in the audit log.
    """

    def __init__(
        self,
        db_path: str | Path = "data/cybertron.db",
    ) -> None:
        self.db_path = Path(db_path)

        if self.db_path.parent:
            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        connection.execute(
            "PRAGMA foreign_keys=ON"
        )

        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    source TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_memories_namespace
                    ON memories(namespace);

                CREATE INDEX IF NOT EXISTS
                    idx_memories_scope
                    ON memories(scope);

                CREATE INDEX IF NOT EXISTS
                    idx_memories_kind
                    ON memories(kind);

                CREATE INDEX IF NOT EXISTS
                    idx_memories_status
                    ON memories(status);

                CREATE INDEX IF NOT EXISTS
                    idx_memories_updated
                    ON memories(updated_at);

                CREATE TABLE IF NOT EXISTS memory_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    detail TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_audit_memory
                    ON memory_audit(memory_id);

                CREATE INDEX IF NOT EXISTS
                    idx_memory_audit_timestamp
                    ON memory_audit(timestamp);
                """
            )

    def _validate_kind(
        self,
        kind: str,
    ) -> str:
        normalized = kind.strip().lower()

        if normalized not in ALLOWED_KINDS:
            raise ValueError(
                "Invalid memory kind: "
                f"{kind}. Allowed: "
                f"{sorted(ALLOWED_KINDS)}"
            )

        return normalized

    def _audit(
        self,
        connection: sqlite3.Connection,
        memory_id: str,
        action: str,
        actor: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO memory_audit (
                memory_id,
                action,
                actor,
                detail,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                action,
                actor,
                json.dumps(
                    detail or {},
                    sort_keys=True,
                ),
                _utc_now(),
            ),
        )

    @staticmethod
    def _row_to_memory(
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        return {
            "id": row["id"],
            "namespace": row["namespace"],
            "scope": row["scope"],
            "kind": row["kind"],
            "content": row["content"],
            "tags": json.loads(
                row["tags"] or "[]"
            ),
            "source": row["source"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def add(
        self,
        *,
        namespace: str,
        scope: str,
        kind: str,
        content: str,
        tags: list[str] | None = None,
        source: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        namespace = namespace.strip()
        scope = scope.strip()
        content = content.strip()
        kind = self._validate_kind(kind)

        if not namespace:
            raise ValueError(
                "namespace is required"
            )

        if not scope:
            raise ValueError(
                "scope is required"
            )

        if not content:
            raise ValueError(
                "content is required"
            )

        normalized_tags = sorted(
            {
                tag.strip().lower()
                for tag in (tags or [])
                if tag.strip()
            }
        )

        memory_id = str(uuid.uuid4())
        timestamp = _utc_now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id,
                    namespace,
                    scope,
                    kind,
                    content,
                    tags,
                    source,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    memory_id,
                    namespace,
                    scope,
                    kind,
                    content,
                    json.dumps(
                        normalized_tags
                    ),
                    source,
                    timestamp,
                    timestamp,
                ),
            )

            self._audit(
                connection,
                memory_id,
                "created",
                actor,
                {
                    "namespace": namespace,
                    "scope": scope,
                    "kind": kind,
                },
            )

        memory = self.get(memory_id)

        if memory is None:
            raise RuntimeError(
                "Memory creation failed"
            )

        return memory

    def get(
        self,
        memory_id: str,
        *,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM memories
            WHERE id = ?
        """

        params: list[Any] = [
            memory_id
        ]

        if not include_deleted:
            query += """
                AND status = 'active'
            """

        with self._connect() as connection:
            row = connection.execute(
                query,
                tuple(params),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_memory(row)

    def search(
        self,
        *,
        query: str | None = None,
        namespace: str | None = None,
        scope: str | None = None,
        kind: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT *
            FROM memories
            WHERE 1 = 1
        """

        params: list[Any] = []

        if not include_deleted:
            sql += """
                AND status = 'active'
            """

        if namespace:
            sql += """
                AND namespace = ?
            """
            params.append(
                namespace.strip()
            )

        if scope:
            sql += """
                AND scope = ?
            """
            params.append(
                scope.strip()
            )

        if kind:
            normalized_kind = (
                self._validate_kind(kind)
            )

            sql += """
                AND kind = ?
            """
            params.append(
                normalized_kind
            )

        if query:
            sql += """
                AND (
                    LOWER(content)
                    LIKE LOWER(?)
                    OR LOWER(tags)
                    LIKE LOWER(?)
                )
            """

            term = (
                "%"
                + query.strip()
                + "%"
            )

            params.extend(
                [
                    term,
                    term,
                ]
            )

        sql += """
            ORDER BY updated_at DESC
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

        memories = [
            self._row_to_memory(row)
            for row in rows
        ]

        if tags:
            required_tags = {
                tag.strip().lower()
                for tag in tags
                if tag.strip()
            }

            memories = [
                memory
                for memory in memories
                if required_tags.issubset(
                    set(memory["tags"])
                )
            ]

        return memories

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        tags: list[str] | None = None,
        source: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        current = self.get(
            memory_id
        )

        if current is None:
            raise KeyError(
                f"Memory not found: "
                f"{memory_id}"
            )

        new_content = (
            content.strip()
            if content is not None
            else current["content"]
        )

        if not new_content:
            raise ValueError(
                "content cannot be empty"
            )

        new_tags = (
            sorted(
                {
                    tag.strip().lower()
                    for tag in tags
                    if tag.strip()
                }
            )
            if tags is not None
            else current["tags"]
        )

        new_source = (
            source
            if source is not None
            else current["source"]
        )

        timestamp = _utc_now()

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE memories
                SET content = ?,
                    tags = ?,
                    source = ?,
                    updated_at = ?
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    new_content,
                    json.dumps(
                        new_tags
                    ),
                    new_source,
                    timestamp,
                    memory_id,
                ),
            )

            self._audit(
                connection,
                memory_id,
                "updated",
                actor,
                {
                    "content_changed":
                        new_content
                        != current["content"],
                    "tags_changed":
                        new_tags
                        != current["tags"],
                    "source_changed":
                        new_source
                        != current["source"],
                },
            )

        updated = self.get(
            memory_id
        )

        if updated is None:
            raise RuntimeError(
                "Memory update failed"
            )

        return updated

    def delete(
        self,
        memory_id: str,
        *,
        actor: str = "system",
    ) -> bool:
        current = self.get(
            memory_id
        )

        if current is None:
            return False

        timestamp = _utc_now()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET status = 'deleted',
                    updated_at = ?
                WHERE id = ?
                  AND status = 'active'
                """,
                (
                    timestamp,
                    memory_id,
                ),
            )

            if cursor.rowcount:
                self._audit(
                    connection,
                    memory_id,
                    "deleted",
                    actor,
                    {
                        "previous_status":
                            "active"
                    },
                )

        return bool(
            cursor.rowcount
        )

    def audit_history(
        self,
        memory_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    memory_id,
                    action,
                    actor,
                    detail,
                    timestamp
                FROM memory_audit
                WHERE memory_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (
                    memory_id,
                    max(
                        1,
                        min(limit, 500),
                    ),
                ),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "memory_id":
                    row["memory_id"],
                "action":
                    row["action"],
                "actor":
                    row["actor"],
                "detail":
                    json.loads(
                        row["detail"] or "{}"
                    ),
                "timestamp":
                    row["timestamp"],
            }
            for row in rows
        ]
