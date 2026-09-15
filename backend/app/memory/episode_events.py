from __future__ import annotations

import json
from typing import Any

from backend.app.events.schema import CoreEvent


def _docker_inventory_summary(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    containers = result.get("containers")
    if not isinstance(containers, list):
        return None

    running = 0
    healthy = 0
    no_health = 0
    stopped = 0
    for container in containers:
        if not isinstance(container, dict):
            continue
        state = str(container.get("State") or "").lower()
        health = str(container.get("HealthStatus") or "none").lower()
        if state == "running":
            running += 1
            if health == "healthy":
                healthy += 1
            elif health in {"", "none"}:
                no_health += 1
        else:
            stopped += 1

    return (
        f"Docker inventory completed: {len(containers)} total; {running} running; "
        f"{healthy} healthy; {no_health} running without explicit health status; "
        f"{stopped} stopped/exited."
    )


def summarize_tool_result(tool_id: str, result: Any) -> str:
    """Create compact episodic text; detailed evidence remains in trace_events."""
    if tool_id == "docker.inventory":
        summary = _docker_inventory_summary(result)
        if summary:
            return summary

    if isinstance(result, dict):
        for key in ("summary", "message", "status", "detail"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:1000]

    compact = json.dumps(result, sort_keys=True, default=str) if result is not None else "Tool completed without a result payload."
    return compact if len(compact) <= 1000 else compact[:1000] + "…"


def episode_from_event(event: CoreEvent) -> dict[str, Any] | None:
    """Project durable lifecycle evidence into a compact operational episode.

    The trace remains authoritative. This projection intentionally captures only
    events with enough provenance to be useful without model interpretation.
    """
    if event.event_type == "tool.completed":
        tool_id = str((event.actor or {}).get("id") or (event.target or {}).get("id") or "unknown-tool")
        agent_id = str((event.target or {}).get("id") or "unknown")
        result = event.metadata.get("result")
        return {
            "prompt": f"Operational tool execution: {tool_id}",
            "outcome": summarize_tool_result(tool_id, result),
            "status": "complete",
            "session_id": event.session_id,
            "trace_id": event.trace_id,
            "agent_id": agent_id,
            "tool_id": tool_id,
            "metadata": {"source_event_id": event.event_id, "source_event_type": event.event_type, "verified": True},
        }

    if event.event_type == "model.error":
        error = str(event.metadata.get("error") or "Model request failed")
        return {
            "prompt": "C.O.R.E. request failure",
            "outcome": error,
            "status": "failed",
            "session_id": event.session_id,
            "trace_id": event.trace_id,
            "agent_id": str((event.target or {}).get("id") or "general"),
            "tool_id": None,
            "metadata": {"source_event_id": event.event_id, "source_event_type": event.event_type},
        }

    return None
