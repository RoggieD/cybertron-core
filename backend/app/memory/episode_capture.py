from __future__ import annotations

from typing import Any

from backend.app.memory.episodic import EpisodicStore, episodic_store


OPERATIONAL_AGENTS = {"system", "infrastructure", "security"}


def should_capture_episode(*, agent_id: str, tool_id: str | None, status: str) -> bool:
    """Capture operational work, not ordinary conversation noise."""
    return bool(tool_id) or agent_id in OPERATIONAL_AGENTS or status in {"failed", "error"}


def capture_episode(
    *,
    prompt: str,
    outcome: str,
    status: str,
    session_id: str | None,
    trace_id: str | None,
    agent_id: str,
    tool_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    store: EpisodicStore = episodic_store,
) -> dict[str, Any] | None:
    if not should_capture_episode(agent_id=agent_id, tool_id=tool_id, status=status):
        return None

    normalized_status = "failed" if status in {"failed", "error"} else status
    importance = 8 if normalized_status == "failed" else (7 if tool_id else 5)
    pain_score = 9 if normalized_status == "failed" else (5 if tool_id else 3)
    tags = [agent_id]
    if tool_id:
        tags.extend(["tool", tool_id])
    if normalized_status == "failed":
        tags.append("failure")

    return store.record(
        prompt=prompt,
        outcome=outcome,
        status=normalized_status,
        session_id=session_id,
        trace_id=trace_id,
        agent_id=agent_id,
        tool_id=tool_id,
        importance=importance,
        pain_score=pain_score,
        tags=tags,
        metadata=metadata or {},
    )
