from __future__ import annotations

import asyncio
import re

from backend.app.events.bus import event_bus
from backend.app.events.schema import CoreEvent
from backend.app.memory import (
    MemoryPolicy,
    MemoryStore,
)


STOPWORDS = {
    "a", "an", "and", "are", "as", "at",
    "be", "about", "do", "does", "for",
    "from", "how", "i", "in", "is", "it",
    "me", "my", "of", "on", "our", "the",
    "this", "to", "what", "with", "you",
    "your",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            value.lower(),
        )
        if (
            len(token) > 1
            and token not in STOPWORDS
        )
    }


def _publish_memory_event(
    event_type: str,
    *,
    status: str,
    metadata: dict | None = None,
) -> None:
    """Publish memory lifecycle telemetry without blocking retrieval.

    Context retrieval is intentionally synchronous today because it reads the
    local SQLite memory store. Chat requests execute inside an asyncio event
    loop, so scheduling the event keeps the retrieval API backward compatible
    while still exposing honest memory activity to the C.O.R.E. event bus.
    """

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    loop.create_task(
        event_bus.publish(
            CoreEvent(
                event_type=event_type,
                actor={
                    "type": "agent",
                    "id": "conversation-context",
                },
                target={
                    "type": "memory",
                    "id": "persistent-memory",
                },
                status=status,
                metadata=metadata or {},
            )
        )
    )


def retrieve_memory_context(
    message: str,
    *,
    limit: int = 5,
) -> list[dict]:
    query_tokens = _tokens(message)

    if not query_tokens:
        return []

    _publish_memory_event(
        "memory.search_started",
        status="running",
        metadata={
            "namespace": "core",
            "scope": "shared,system",
            "query_token_count": len(query_tokens),
            "limit": limit,
        },
    )

    store = MemoryStore(
        "data/cybertron.db"
    )
    policy = MemoryPolicy(
        "data/cybertron.db"
    )

    ranked: list[tuple[int, dict]] = []

    for scope in (
        "shared",
        "system",
    ):
        decision = policy.evaluate(
            operation="read",
            actor_type="agent",
            actor_id="conversation-context",
            namespace="core",
            scope=scope,
            source="conversation-context",
        )

        if not decision.allowed:
            continue

        memories = store.search(
            scope=scope,
            limit=250,
        )

        for memory in memories:
            searchable = " ".join(
                [
                    memory.get(
                        "content",
                        "",
                    ),
                    " ".join(
                        memory.get(
                            "tags",
                            [],
                        )
                    ),
                    memory.get(
                        "namespace",
                        "",
                    ),
                    memory.get(
                        "source",
                        "",
                    )
                    or "",
                ]
            )

            memory_tokens = _tokens(
                searchable
            )

            overlap = (
                query_tokens
                & memory_tokens
            )

            if not overlap:
                continue

            score = len(overlap)

            ranked.append(
                (
                    score,
                    memory,
                )
            )

    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].get(
                "updated_at",
                "",
            ),
        ),
        reverse=True,
    )

    seen = set()
    results = []

    for _, memory in ranked:
        memory_id = memory["id"]

        if memory_id in seen:
            continue

        seen.add(memory_id)
        results.append(memory)

        if len(results) >= limit:
            break

    result_scopes = sorted(
        {
            str(memory.get("scope", "unknown"))
            for memory in results
        }
    )
    result_kinds = sorted(
        {
            str(memory.get("kind", "unknown"))
            for memory in results
        }
    )

    _publish_memory_event(
        "memory.search_completed",
        status="complete",
        metadata={
            "namespace": "core",
            "scope": ",".join(result_scopes) if result_scopes else "none",
            "kinds": result_kinds,
            "result_count": len(results),
        },
    )

    return results


def format_memory_context(
    message: str,
) -> str:
    memories = retrieve_memory_context(
        message
    )

    if not memories:
        return ""

    lines = [
        "VERIFIED PERSISTENT MEMORY — CONTEXT RETRIEVAL",
        f"Context records retrieved: {len(memories)}",
        (
            "The following records were retrieved from policy-authorized "
            "persistent memory for this conversation."
        ),
        (
            "Treat them as verified stored context, not as live system "
            "measurements."
        ),
        (
            "IMPORTANT: If a separate memory.search tool invocation returns "
            "zero matches, that means only that specific tool query found no "
            "additional matches. It does NOT negate these retrieved context "
            "records and does NOT mean persistent memory is empty."
        ),
    ]

    for memory in memories:
        lines.append(
            "- "
            f"[{memory['kind']}] "
            f"{memory['content']} "
            f"(scope: {memory.get('scope') or 'unknown'}; "
            f"source: {memory.get('source') or 'unknown'})"
        )

    return "\n".join(lines)
