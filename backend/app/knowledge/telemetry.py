"""Request-scoped provenance for reference context; never publish excerpts."""
from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar

from backend.app.knowledge.retrieval import DEFAULT_REGISTRY, matching_kbs, retrieve_knowledge, format_knowledge_context
from backend.app.memory.context_budget import allocate_context_budget, estimate_tokens

_pending: ContextVar[asyncio.Task | None] = ContextVar("knowledge_telemetry", default=None)


async def flush_knowledge_telemetry() -> None:
    task = _pending.get()
    _pending.set(None)
    if task is not None:
        await task


def build_knowledge_context(message, *, retriever=retrieve_knowledge, registry_path=DEFAULT_REGISTRY,
                            session_id=None, trace_id=None) -> str:
    from backend.app.events.bus import event_bus
    from backend.app.events.schema import CoreEvent

    kbs = matching_kbs(message, registry_path=registry_path)
    def event(kind, metadata):
        return CoreEvent(event_type=f"knowledge.{kind}", session_id=session_id, trace_id=trace_id,
                         actor={"type": "agent", "id": "conversation-context"},
                         target={"type": "knowledge", "id": "reference-knowledge"},
                         status="running" if kind == "search_started" else "complete",
                         metadata={"reference_only": True, **metadata})

    searched = [{"id": kb["id"], "name": kb["name"]} for kb in kbs]
    events = [event("search_started", {"knowledge_bases": searched})]
    results = retriever(message)
    selection = []
    budget = allocate_context_budget()["knowledge"]
    context = format_knowledge_context(results, token_budget=budget, selection=selection)
    if not kbs and not results:
        return context
    events.append(event("search_completed", {"matched_count": len(results)}))
    events.append(event("context_selected", {
        "knowledge_bases": searched, "matched_count": len(results),
        "selected_count": len(selection), "omitted_count": len(results) - len(selection),
        "token_budget": budget, "estimated_tokens": estimate_tokens(context), "sources": selection,
    }))

    async def publish():
        try:
            for item in events:
                await event_bus.publish(item)
        except Exception:
            logging.getLogger(__name__).exception("Knowledge provenance telemetry failed")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        _pending.set(loop.create_task(publish()))
    return context
