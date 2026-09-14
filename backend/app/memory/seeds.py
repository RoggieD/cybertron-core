from __future__ import annotations

from backend.app.memory.store import MemoryStore


VERIFIED_MEMORIES = [
    {
        "namespace": "core",
        "scope": "shared",
        "kind": "fact",
        "content": (
            "CyberTron C.O.R.E. is the CyberTron "
            "Orchestration & Reasoning Engine, a local-first "
            "agent orchestration platform."
        ),
        "tags": [
            "core",
            "cybertron",
            "architecture",
        ],
        "source": "core-bootstrap",
    },
    {
        "namespace": "core",
        "scope": "system",
        "kind": "fact",
        "content": (
            "C.O.R.E. persistent memory is backed by SQLite "
            "and includes an append-only audit trail for "
            "memory mutations."
        ),
        "tags": [
            "core",
            "memory",
            "sqlite",
            "audit",
        ],
        "source": "memory-engine",
    },
    {
        "namespace": "operations",
        "scope": "system",
        "kind": "fact",
        "content": (
            "C.O.R.E. persists system telemetry history "
            "for operational monitoring and trend analysis."
        ),
        "tags": [
            "telemetry",
            "monitoring",
            "operations",
        ],
        "source": "telemetry-subsystem",
    },
    {
        "namespace": "operations",
        "scope": "system",
        "kind": "fact",
        "content": (
            "C.O.R.E. includes persistent incident history, "
            "incident lifecycle tracking, acknowledgement, "
            "search, export, analytics, and deterministic "
            "time-aware incident intelligence."
        ),
        "tags": [
            "incident",
            "analytics",
            "monitoring",
            "operations",
        ],
        "source": "incident-subsystem",
    },
    {
        "namespace": "providers",
        "scope": "shared",
        "kind": "fact",
        "content": (
            "Ollama is the default local model provider for "
            "C.O.R.E., while the provider layer is designed "
            "to remain model-independent."
        ),
        "tags": [
            "ollama",
            "model",
            "provider",
            "local-ai",
        ],
        "source": "provider-layer",
    },
    {
        "namespace": "security",
        "scope": "system",
        "kind": "fact",
        "content": (
            "Agent-facing persistent memory reads are currently "
            "restricted to system and shared scopes."
        ),
        "tags": [
            "memory",
            "security",
            "policy",
            "scope",
        ],
        "source": "memory-policy",
    },
    {
        "namespace": "security",
        "scope": "system",
        "kind": "fact",
        "content": (
            "Models have no direct authority to mutate "
            "C.O.R.E. persistent memory. Persistent writes "
            "must pass through an authorized policy-controlled "
            "execution path."
        ),
        "tags": [
            "memory",
            "security",
            "policy",
            "model",
        ],
        "source": "memory-policy",
    },
]


def seed_verified_memories(
    store: MemoryStore | None = None,
) -> dict:
    store = store or MemoryStore(
        "data/cybertron.db"
    )

    created = 0
    existing = 0

    for item in VERIFIED_MEMORIES:
        matches = store.search(
            query=item["content"],
            namespace=item["namespace"],
            scope=item["scope"],
            kind=item["kind"],
            limit=10,
        )

        exact = any(
            memory["content"]
            == item["content"]
            for memory in matches
        )

        if exact:
            existing += 1
            continue

        store.add(
            namespace=item["namespace"],
            scope=item["scope"],
            kind=item["kind"],
            content=item["content"],
            tags=item["tags"],
            source=item["source"],
            actor="system:verified-bootstrap",
        )

        created += 1

    return {
        "created": created,
        "existing": existing,
        "total": len(VERIFIED_MEMORIES),
    }
