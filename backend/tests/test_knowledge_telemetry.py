import asyncio
import json

from backend.app.knowledge.retrieval import format_knowledge_context
from backend.app.knowledge.telemetry import build_knowledge_context, flush_knowledge_telemetry
from backend.app.memory.context_budget import estimate_tokens


def test_budget_preserves_citation_and_reports_only_packed_sources():
    records = [{"kb": "kb", "name": "Reference", "path": "rag.md", "section": "Hybrid search",
                "chunk_id": "chunk-1", "content": "long reference " * 1000},
               {"path": "omitted.md", "content": "another reference"}]
    selection = []
    context = format_knowledge_context(records, token_budget=200, selection=selection)
    assert estimate_tokens(context) <= 200
    assert "NOT LIVE SYSTEM EVIDENCE" in context
    assert "Source: rag.md; chunk: chunk-1" in context
    assert "[TRUNCATED]" in context
    assert len(selection) == 1 and selection[0]["excerpt_shortened"]
    assert "content" not in selection[0]
    empty = []
    assert format_knowledge_context(records, token_budget=1, selection=empty) == ""
    assert empty == []


def test_request_telemetry_order_no_content_and_no_unrelated_search(tmp_path, monkeypatch):
    from backend.app.events.bus import event_bus
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"knowledge_bases": [{"id": "kb", "name": "Test KB", "enabled": True,
                                                       "triggers": ["documentation"]}]}))
    events = []
    async def publish(event):
        events.append(event)
    monkeypatch.setattr(event_bus, "publish", publish)
    async def run():
        context = build_knowledge_context("documentation", registry_path=registry, session_id="s", trace_id="t",
            retriever=lambda _: [{"kb": "kb", "name": "Test KB", "path": "rag.md", "chunk_id": "c1",
                                  "content": "PRIVATE EXCERPT"}])
        await flush_knowledge_telemetry()
        assert "PRIVATE EXCERPT" in context
        assert [e.event_type for e in events] == ["knowledge.search_started", "knowledge.search_completed", "knowledge.context_selected"]
        assert all(e.trace_id == "t" and e.session_id == "s" for e in events)
        metadata = events[-1].metadata
        assert metadata["selected_count"] == 1
        assert metadata["knowledge_bases"] == [{"id": "kb", "name": "Test KB"}]
        assert metadata["sources"][0]["chunk_id"] == "c1"
        assert "PRIVATE EXCERPT" not in json.dumps([e.metadata for e in events])
        events.clear()
        build_knowledge_context("hello", registry_path=registry, retriever=lambda _: [])
        await flush_knowledge_telemetry()
        assert events == []
        build_knowledge_context("documentation", registry_path=registry, retriever=lambda _: [])
        await flush_knowledge_telemetry()
        assert events[-1].metadata["selected_count"] == 0
        assert events[-1].metadata["estimated_tokens"] == 0
    asyncio.run(run())
