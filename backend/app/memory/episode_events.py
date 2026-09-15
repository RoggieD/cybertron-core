from __future__ import annotations

import json
from typing import Any

from backend.app.events.schema import CoreEvent


def episode_from_event(event: CoreEvent) -> dict[str, Any] | None:
    """Project durable lifecycle evidence into a compact operational episode.

    The trace remains authoritative. This projection intentionally captures only
    events with enough provenance to be useful without model interpretation.
    """
    if event.event_type == "tool.completed":
        tool_id = str((event.actor or {}).get("id") or (event.target or {}).get("id") or "unknown-tool")
        agent_id = str((event.target or {}).get("id") or "unknown")
        result = event.metadata.get("result")
        outcome = json.dumps(result, sort_keys=True, default=str) if result is not None else "Tool completed without a result payload."
        if len(outcome) > 4000:
            outcome = outcome[:4000] + "…"
        return {
            "prompt": f"Operational tool execution: {tool_id}",
            "outcome": outcome,
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
