from __future__ import annotations

import json
import sqlite3
import uuid

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


ActorType = Literal[
    "system",
    "user",
    "agent",
    "tool",
    "model",
]

Operation = Literal[
    "read",
    "create",
    "update",
    "delete",
]


@dataclass(frozen=True)
class MemoryPolicyDecision:
    decision_id: str
    allowed: bool
    requires_confirmation: bool
    reason: str
    operation: str
    actor_type: str
    actor_id: str
    namespace: str
    scope: str
    kind: str | None

    def to_dict(self) -> dict:
        return asdict(self)


class MemoryPolicy:
    """
    Deterministic authorization policy for C.O.R.E. memory.

    Important:
    - Models never receive direct memory mutation authority.
    - Private user scopes are not automatically visible to agents.
    - Agent automatic writes are intentionally narrow.
    - Destructive mutations require stronger authorization.
    """

    AUTO_AGENT_KINDS = {
        "observation",
        "summary",
    }

    CONFIRM_AGENT_KINDS = {
        "fact",
        "preference",
        "decision",
    }

    VALID_OPERATIONS = {
        "read",
        "create",
        "update",
        "delete",
    }

    VALID_ACTOR_TYPES = {
        "system",
        "user",
        "agent",
        "tool",
        "model",
    }

    def __init__(
        self,
        db_path: str | Path = "data/cybertron.db",
    ) -> None:
        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
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
                    memory_policy_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        decision_id TEXT NOT NULL UNIQUE,
                        allowed INTEGER NOT NULL,
                        requires_confirmation INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        actor_type TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        namespace TEXT NOT NULL,
                        scope TEXT NOT NULL,
                        kind TEXT,
                        source TEXT,
                        confirmed INTEGER NOT NULL,
                        timestamp TEXT NOT NULL
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_policy_decision
                    ON memory_policy_audit(decision_id);

                CREATE INDEX IF NOT EXISTS
                    idx_memory_policy_actor
                    ON memory_policy_audit(
                        actor_type,
                        actor_id
                    );

                CREATE INDEX IF NOT EXISTS
                    idx_memory_policy_timestamp
                    ON memory_policy_audit(timestamp);
                """
            )

    def _record(
        self,
        decision: MemoryPolicyDecision,
        *,
        source: str | None,
        confirmed: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_policy_audit (
                    decision_id,
                    allowed,
                    requires_confirmation,
                    reason,
                    operation,
                    actor_type,
                    actor_id,
                    namespace,
                    scope,
                    kind,
                    source,
                    confirmed,
                    timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.decision_id,
                    int(decision.allowed),
                    int(
                        decision.requires_confirmation
                    ),
                    decision.reason,
                    decision.operation,
                    decision.actor_type,
                    decision.actor_id,
                    decision.namespace,
                    decision.scope,
                    decision.kind,
                    source,
                    int(confirmed),
                    self._utc_now(),
                ),
            )

    def _decision(
        self,
        *,
        allowed: bool,
        requires_confirmation: bool,
        reason: str,
        operation: str,
        actor_type: str,
        actor_id: str,
        namespace: str,
        scope: str,
        kind: str | None,
        source: str | None,
        confirmed: bool,
    ) -> MemoryPolicyDecision:
        decision = MemoryPolicyDecision(
            decision_id=str(uuid.uuid4()),
            allowed=allowed,
            requires_confirmation=(
                requires_confirmation
            ),
            reason=reason,
            operation=operation,
            actor_type=actor_type,
            actor_id=actor_id,
            namespace=namespace,
            scope=scope,
            kind=kind,
        )

        self._record(
            decision,
            source=source,
            confirmed=confirmed,
        )

        return decision

    @staticmethod
    def _scope_owner(
        scope: str,
        prefix: str,
    ) -> str | None:
        expected = f"{prefix}:"

        if not scope.startswith(expected):
            return None

        owner = scope[
            len(expected):
        ].strip()

        return owner or None

    def evaluate(
        self,
        *,
        operation: Operation,
        actor_type: ActorType,
        actor_id: str,
        namespace: str,
        scope: str,
        kind: str | None = None,
        source: str | None = None,
        confirmed: bool = False,
    ) -> MemoryPolicyDecision:
        operation = operation.strip().lower()
        actor_type = actor_type.strip().lower()
        actor_id = actor_id.strip()
        namespace = namespace.strip()
        scope = scope.strip()

        if kind is not None:
            kind = kind.strip().lower()

        if operation not in self.VALID_OPERATIONS:
            raise ValueError(
                f"Invalid operation: {operation}"
            )

        if actor_type not in self.VALID_ACTOR_TYPES:
            raise ValueError(
                f"Invalid actor type: {actor_type}"
            )

        if not actor_id:
            raise ValueError(
                "actor_id is required"
            )

        if not namespace:
            raise ValueError(
                "namespace is required"
            )

        if not scope:
            raise ValueError(
                "scope is required"
            )

        user_owner = self._scope_owner(
            scope,
            "user",
        )

        agent_owner = self._scope_owner(
            scope,
            "agent",
        )

        # -------------------------------------------------
        # Models never directly manipulate persistent memory.
        # They must act through an authorized agent/tool path.
        # -------------------------------------------------

        if actor_type == "model":
            return self._decision(
                allowed=False,
                requires_confirmation=False,
                reason=(
                    "Models have no direct persistent "
                    "memory authority."
                ),
                operation=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                namespace=namespace,
                scope=scope,
                kind=kind,
                source=source,
                confirmed=confirmed,
            )

        # -------------------------------------------------
        # System principal
        # -------------------------------------------------

        if actor_type == "system":
            return self._decision(
                allowed=True,
                requires_confirmation=False,
                reason=(
                    "Trusted system principal."
                ),
                operation=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                namespace=namespace,
                scope=scope,
                kind=kind,
                source=source,
                confirmed=confirmed,
            )

        # -------------------------------------------------
        # READ POLICY
        # -------------------------------------------------

        if operation == "read":
            if scope in {
                "system",
                "shared",
            }:
                return self._decision(
                    allowed=True,
                    requires_confirmation=False,
                    reason=(
                        "Shared/system memory is readable "
                        "by authenticated C.O.R.E. actors."
                    ),
                    operation=operation,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    namespace=namespace,
                    scope=scope,
                    kind=kind,
                    source=source,
                    confirmed=confirmed,
                )

            if actor_type == "user":
                if user_owner == actor_id:
                    return self._decision(
                        allowed=True,
                        requires_confirmation=False,
                        reason=(
                            "User may read their private "
                            "memory scope."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

            if actor_type == "agent":
                if agent_owner == actor_id:
                    return self._decision(
                        allowed=True,
                        requires_confirmation=False,
                        reason=(
                            "Agent may read its own "
                            "memory scope."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

            return self._decision(
                allowed=False,
                requires_confirmation=False,
                reason=(
                    "Actor is not authorized to read "
                    "this private memory scope."
                ),
                operation=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                namespace=namespace,
                scope=scope,
                kind=kind,
                source=source,
                confirmed=confirmed,
            )

        # -------------------------------------------------
        # PRIVATE USER MEMORY
        # -------------------------------------------------

        if user_owner is not None:
            if (
                actor_type != "user"
                or user_owner != actor_id
            ):
                return self._decision(
                    allowed=False,
                    requires_confirmation=False,
                    reason=(
                        "Private user memory may only "
                        "be mutated by its owning user."
                    ),
                    operation=operation,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    namespace=namespace,
                    scope=scope,
                    kind=kind,
                    source=source,
                    confirmed=confirmed,
                )

            if operation in {
                "update",
                "delete",
            } and not confirmed:
                return self._decision(
                    allowed=False,
                    requires_confirmation=True,
                    reason=(
                        "Updating or deleting persistent "
                        "user memory requires confirmation."
                    ),
                    operation=operation,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    namespace=namespace,
                    scope=scope,
                    kind=kind,
                    source=source,
                    confirmed=confirmed,
                )

            return self._decision(
                allowed=True,
                requires_confirmation=False,
                reason=(
                    "Owning user authorized the "
                    "private memory mutation."
                ),
                operation=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                namespace=namespace,
                scope=scope,
                kind=kind,
                source=source,
                confirmed=confirmed,
            )

        # -------------------------------------------------
        # AGENT MEMORY
        # -------------------------------------------------

        if actor_type == "agent":
            if agent_owner is not None:
                if agent_owner != actor_id:
                    return self._decision(
                        allowed=False,
                        requires_confirmation=False,
                        reason=(
                            "Agent cannot mutate another "
                            "agent's private memory."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                if operation in {
                    "update",
                    "delete",
                }:
                    if not confirmed:
                        return self._decision(
                            allowed=False,
                            requires_confirmation=True,
                            reason=(
                                "Agent memory mutation "
                                "requires confirmation."
                            ),
                            operation=operation,
                            actor_type=actor_type,
                            actor_id=actor_id,
                            namespace=namespace,
                            scope=scope,
                            kind=kind,
                            source=source,
                            confirmed=confirmed,
                        )

                    return self._decision(
                        allowed=True,
                        requires_confirmation=False,
                        reason=(
                            "Confirmed mutation of the "
                            "agent's own memory."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                if not source:
                    return self._decision(
                        allowed=False,
                        requires_confirmation=False,
                        reason=(
                            "Automatic agent memory writes "
                            "require provenance/source."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                if kind in self.AUTO_AGENT_KINDS:
                    return self._decision(
                        allowed=True,
                        requires_confirmation=False,
                        reason=(
                            "Agent may automatically store "
                            "scoped observations/summaries "
                            "with provenance."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                if kind in self.CONFIRM_AGENT_KINDS:
                    if not confirmed:
                        return self._decision(
                            allowed=False,
                            requires_confirmation=True,
                            reason=(
                                "Facts, preferences and "
                                "decisions require explicit "
                                "confirmation before an agent "
                                "may persist them."
                            ),
                            operation=operation,
                            actor_type=actor_type,
                            actor_id=actor_id,
                            namespace=namespace,
                            scope=scope,
                            kind=kind,
                            source=source,
                            confirmed=confirmed,
                        )

                    return self._decision(
                        allowed=True,
                        requires_confirmation=False,
                        reason=(
                            "Confirmed agent memory write."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

            # Agents writing system/shared memory always
            # require an explicit approval boundary.
            if scope in {
                "system",
                "shared",
            }:
                if not confirmed:
                    return self._decision(
                        allowed=False,
                        requires_confirmation=True,
                        reason=(
                            "Agent writes to shared/system "
                            "memory require confirmation."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                if not source:
                    return self._decision(
                        allowed=False,
                        requires_confirmation=False,
                        reason=(
                            "Confirmed agent writes still "
                            "require provenance/source."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                return self._decision(
                    allowed=True,
                    requires_confirmation=False,
                    reason=(
                        "Confirmed agent write to "
                        "shared/system memory."
                    ),
                    operation=operation,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    namespace=namespace,
                    scope=scope,
                    kind=kind,
                    source=source,
                    confirmed=confirmed,
                )

        # -------------------------------------------------
        # TOOL PRINCIPALS
        # -------------------------------------------------

        if actor_type == "tool":
            return self._decision(
                allowed=False,
                requires_confirmation=False,
                reason=(
                    "Tools do not receive implicit "
                    "persistent-memory mutation authority."
                ),
                operation=operation,
                actor_type=actor_type,
                actor_id=actor_id,
                namespace=namespace,
                scope=scope,
                kind=kind,
                source=source,
                confirmed=confirmed,
            )

        # -------------------------------------------------
        # USER WRITES TO SYSTEM/SHARED
        # -------------------------------------------------

        if actor_type == "user":
            if scope == "shared":
                return self._decision(
                    allowed=True,
                    requires_confirmation=False,
                    reason=(
                        "User may create or mutate "
                        "explicit shared memory."
                    ),
                    operation=operation,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    namespace=namespace,
                    scope=scope,
                    kind=kind,
                    source=source,
                    confirmed=confirmed,
                )

            if scope == "system":
                if not confirmed:
                    return self._decision(
                        allowed=False,
                        requires_confirmation=True,
                        reason=(
                            "System memory mutation "
                            "requires explicit confirmation."
                        ),
                        operation=operation,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        namespace=namespace,
                        scope=scope,
                        kind=kind,
                        source=source,
                        confirmed=confirmed,
                    )

                return self._decision(
                    allowed=True,
                    requires_confirmation=False,
                    reason=(
                        "Confirmed user mutation of "
                        "system memory."
                    ),
                    operation=operation,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    namespace=namespace,
                    scope=scope,
                    kind=kind,
                    source=source,
                    confirmed=confirmed,
                )

        return self._decision(
            allowed=False,
            requires_confirmation=False,
            reason=(
                "No memory policy rule authorizes "
                "this operation."
            ),
            operation=operation,
            actor_type=actor_type,
            actor_id=actor_id,
            namespace=namespace,
            scope=scope,
            kind=kind,
            source=source,
            confirmed=confirmed,
        )

    def audit_history(
        self,
        *,
        limit: int = 100,
    ) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM memory_policy_audit
                ORDER BY id DESC
                LIMIT ?
                """,
                (
                    max(
                        1,
                        min(limit, 1000),
                    ),
                ),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "decision_id":
                    row["decision_id"],
                "allowed":
                    bool(row["allowed"]),
                "requires_confirmation":
                    bool(
                        row[
                            "requires_confirmation"
                        ]
                    ),
                "reason":
                    row["reason"],
                "operation":
                    row["operation"],
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
                "source":
                    row["source"],
                "confirmed":
                    bool(row["confirmed"]),
                "timestamp":
                    row["timestamp"],
            }
            for row in rows
        ]
