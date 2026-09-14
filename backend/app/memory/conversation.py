from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.memory.orchestrator import (
    MemoryWriteOrchestrator,
)


@dataclass(frozen=True)
class MemoryCandidate:
    kind: str
    content: str
    trigger: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "content": self.content,
            "trigger": self.trigger,
        }


_PATTERNS: tuple[
    tuple[str, str, str],
    ...
] = (
    (
        r"^\s*(?:please\s+)?remember\s+that\s+(.+?)\s*$",
        "fact",
        "explicit-remember",
    ),
    (
        r"^\s*(?:please\s+)?remember\s+(.+?)\s*$",
        "fact",
        "explicit-remember",
    ),
    (
        r"^\s*(?:please\s+)?note\s+that\s+(.+?)\s*$",
        "fact",
        "explicit-note",
    ),
    (
        r"^\s*i\s+prefer\s+(.+?)\s*$",
        "preference",
        "explicit-preference",
    ),
    (
        r"^\s*my\s+preference\s+is\s+(.+?)\s*$",
        "preference",
        "explicit-preference",
    ),
    (
        r"^\s*we\s+decided\s+(?:that\s+)?(.+?)\s*$",
        "decision",
        "explicit-decision",
    ),
    (
        r"^\s*from\s+now\s+on[,:\s]+(.+?)\s*$",
        "preference",
        "future-preference",
    ),
)


def detect_memory_candidate(
    message: str,
) -> MemoryCandidate | None:
    text = message.strip()

    if not text:
        return None

    for pattern, kind, trigger in _PATTERNS:
        match = re.match(
            pattern,
            text,
            re.IGNORECASE,
        )

        if not match:
            continue

        content = match.group(1).strip()

        content = content.rstrip(
            " \t\r\n"
        )

        if not content:
            return None

        return MemoryCandidate(
            kind=kind,
            content=content,
            trigger=trigger,
        )

    return None


def _proposal_duplicate(
    orchestrator: MemoryWriteOrchestrator,
    *,
    content: str,
    kind: str,
    namespace: str,
    scope: str,
) -> dict | None:
    normalized_content = (
        content.strip().casefold()
    )

    proposals = (
        orchestrator.list_proposals(
            limit=500
        )
    )

    for proposal in proposals:
        if (
            proposal["kind"] == kind
            and proposal["namespace"]
            == namespace
            and proposal["scope"] == scope
            and proposal["content"]
            .strip()
            .casefold()
            == normalized_content
            and proposal["status"]
            in {
                "pending",
                "committed",
            }
        ):
            return proposal

    memories = (
        orchestrator.store.search(
            namespace=namespace,
            scope=scope,
            kind=kind,
            limit=500,
        )
    )

    for memory in memories:
        if (
            memory["content"]
            .strip()
            .casefold()
            == normalized_content
        ):
            return {
                "status": "committed",
                "memory_id": memory["id"],
                "duplicate": True,
            }

    return None


def capture_user_memory(
    message: str,
    *,
    agent_id: str = "general",
    namespace: str = "conversation",
    orchestrator: (
        MemoryWriteOrchestrator
        | None
    ) = None,
) -> dict:
    candidate = detect_memory_candidate(
        message
    )

    if candidate is None:
        return {
            "detected": False,
            "proposal": None,
        }

    orchestrator = (
        orchestrator
        or MemoryWriteOrchestrator(
            "data/cybertron.db"
        )
    )

    scope = "shared"

    duplicate = _proposal_duplicate(
        orchestrator,
        content=candidate.content,
        kind=candidate.kind,
        namespace=namespace,
        scope=scope,
    )

    if duplicate is not None:
        return {
            "detected": True,
            "duplicate": True,
            "candidate":
                candidate.to_dict(),
            "proposal": duplicate,
        }

    proposal = orchestrator.propose(
        actor_type="agent",
        actor_id=agent_id,
        namespace=namespace,
        scope=scope,
        kind=candidate.kind,
        content=candidate.content,
        tags=[
            "conversation",
            candidate.trigger,
        ],
        source=(
            "conversation:user-explicit"
        ),
    )

    return {
        "detected": True,
        "duplicate": False,
        "candidate":
            candidate.to_dict(),
        "proposal": proposal,
    }
