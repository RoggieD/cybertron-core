from __future__ import annotations

import re

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


def retrieve_memory_context(
    message: str,
    *,
    limit: int = 5,
) -> list[dict]:
    query_tokens = _tokens(message)

    if not query_tokens:
        return []

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
        "VERIFIED PERSISTENT MEMORY:",
        (
            "The following records were retrieved "
            "from policy-authorized persistent memory."
        ),
        (
            "Treat them as stored context, not as "
            "live system measurements."
        ),
    ]

    for memory in memories:
        lines.append(
            "- "
            f"[{memory['kind']}] "
            f"{memory['content']} "
            f"(source: "
            f"{memory.get('source') or 'unknown'})"
        )

    return "\n".join(lines)
