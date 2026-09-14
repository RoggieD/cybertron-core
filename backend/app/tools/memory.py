from __future__ import annotations

from typing import Any

from backend.app.memory import (
    MemoryPolicy,
    MemoryStore,
)


PUBLIC_AGENT_SCOPES = {
    "system",
    "shared",
}


def _default_store() -> MemoryStore:
    return MemoryStore(
        "data/cybertron.db"
    )


def _default_policy() -> MemoryPolicy:
    return MemoryPolicy(
        "data/cybertron.db"
    )


def _memory_search(
    *,
    store: MemoryStore,
    policy: MemoryPolicy,
    query: str | None = None,
    namespace: str | None = None,
    scope: str = "shared",
    kind: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    scope = scope.strip().lower()

    if scope not in PUBLIC_AGENT_SCOPES:
        return {
            "allowed": False,
            "reason": (
                "Agent-facing memory.search is limited "
                "to system/shared scopes."
            ),
            "scope": scope,
            "memories": [],
        }

    decision = policy.evaluate(
        operation="read",
        actor_type="agent",
        actor_id="core-readonly",
        namespace=(
            namespace
            or "core"
        ),
        scope=scope,
        kind=kind,
        source="memory.search",
    )

    if not decision.allowed:
        return {
            "allowed": False,
            "reason": decision.reason,
            "decision_id":
                decision.decision_id,
            "scope": scope,
            "memories": [],
        }

    memories = store.search(
        query=query,
        namespace=namespace,
        scope=scope,
        kind=kind,
        tags=tags,
        limit=max(
            1,
            min(limit, 100),
        ),
    )

    return {
        "allowed": True,
        "decision_id":
            decision.decision_id,
        "scope": scope,
        "count": len(memories),
        "memories": memories,
    }


def _memory_read(
    *,
    store: MemoryStore,
    policy: MemoryPolicy,
    memory_id: str,
) -> dict[str, Any]:
    memory = store.get(
        memory_id
    )

    if memory is None:
        return {
            "allowed": False,
            "found": False,
            "reason": "Memory not found.",
            "memory": None,
        }

    scope = memory["scope"]

    if scope not in PUBLIC_AGENT_SCOPES:
        return {
            "allowed": False,
            "found": True,
            "reason": (
                "Agent-facing memory.read cannot "
                "access private memory scopes."
            ),
            "memory": None,
        }

    decision = policy.evaluate(
        operation="read",
        actor_type="agent",
        actor_id="core-readonly",
        namespace=memory["namespace"],
        scope=scope,
        kind=memory["kind"],
        source="memory.read",
    )

    if not decision.allowed:
        return {
            "allowed": False,
            "found": True,
            "reason": decision.reason,
            "decision_id":
                decision.decision_id,
            "memory": None,
        }

    return {
        "allowed": True,
        "found": True,
        "decision_id":
            decision.decision_id,
        "memory": memory,
    }


async def memory_search(
    query: str | None = None,
    namespace: str | None = None,
    scope: str = "shared",
    kind: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    return _memory_search(
        store=_default_store(),
        policy=_default_policy(),
        query=query,
        namespace=namespace,
        scope=scope,
        kind=kind,
        tags=tags,
        limit=limit,
    )


async def memory_read(
    memory_id: str,
) -> dict[str, Any]:
    return _memory_read(
        store=_default_store(),
        policy=_default_policy(),
        memory_id=memory_id,
    )
