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


def _normalize_memory_text(
    value: str,
) -> str:
    import re

    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower(),
    )


def _memory_query_tokens(
    query: str,
) -> list[str]:
    import re

    stopwords = {
        "a",
        "an",
        "and",
        "about",
        "anything",
        "for",
        "in",
        "of",
        "on",
        "the",
        "to",
        "your",
    }

    raw = re.findall(
        r"[a-z0-9]+",
        query.lower(),
    )

    tokens = [
        token
        for token in raw
        if token not in stopwords
    ]

    # C.O.R.E. becomes c,o,r,e with ordinary tokenization.
    # Preserve the collapsed form as a useful deterministic
    # search token.
    collapsed = _normalize_memory_text(
        query
    )

    if (
        len(raw) > 1
        and all(
            len(token) == 1
            for token in raw
        )
        and collapsed
    ):
        return [collapsed]

    return tokens or (
        [collapsed]
        if collapsed
        else []
    )


def _matches_memory_query(
    memory: dict,
    query: str,
) -> bool:
    tokens = _memory_query_tokens(
        query
    )

    if not tokens:
        return True

    searchable = " ".join(
        [
            str(
                memory.get(
                    "content",
                    "",
                )
            ),
            " ".join(
                memory.get("tags")
                or []
            ),
            str(
                memory.get(
                    "source",
                    "",
                )
                or ""
            ),
            str(
                memory.get(
                    "namespace",
                    "",
                )
            ),
        ]
    )

    normalized = _normalize_memory_text(
        searchable
    )

    return all(
        _normalize_memory_text(token)
        in normalized
        for token in tokens
    )


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

    if scope == "all":
        combined = []

        for public_scope in (
            "shared",
            "system",
        ):
            result = _memory_search(
                store=store,
                policy=policy,
                query=query,
                namespace=namespace,
                scope=public_scope,
                kind=kind,
                tags=tags,
                limit=limit,
            )

            if result.get("allowed"):
                combined.extend(
                    result.get("memories")
                    or []
                )

        combined.sort(
            key=lambda item: item.get(
                "updated_at",
                "",
            ),
            reverse=True,
        )

        combined = combined[
            :max(
                1,
                min(limit, 100),
            )
        ]

        return {
            "allowed": True,
            "scope": "all",
            "count": len(combined),
            "memories": combined,
        }

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

    requested_limit = max(
        1,
        min(limit, 100),
    )

    memories = store.search(
        query=query,
        namespace=namespace,
        scope=scope,
        kind=kind,
        tags=tags,
        limit=requested_limit,
    )

    # SQLite LIKE remains the fast path. If the query is
    # semantically simple but not a literal substring,
    # perform deterministic normalized token matching over
    # the allowed scope.
    if query and not memories:
        candidates = store.search(
            query=None,
            namespace=namespace,
            scope=scope,
            kind=kind,
            tags=tags,
            limit=500,
        )

        memories = [
            memory
            for memory in candidates
            if _matches_memory_query(
                memory,
                query,
            )
        ][
            :requested_limit
        ]

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
