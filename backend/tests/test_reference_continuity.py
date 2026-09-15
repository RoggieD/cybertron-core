import asyncio
import importlib
import json

import pytest

from backend.app.knowledge import citations
from backend.app.knowledge.telemetry import build_knowledge_context, flush_knowledge_telemetry

FOLLOWUP = "Cite the source paths and chunk IDs supporting your previous answer. Do not invent citations."
SOURCE = {"kb": "open-webui", "name": "Open WebUI", "path": "docs/rag.md", "chunk_id": "original-1",
          "section": "Hybrid", "content": "PRIVATE REFERENCE CONTENT"}


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(citations, "DATABASE", tmp_path / "citations.db")
    citations.reset_receipt()


def test_only_packed_metadata_is_retained_without_document_content(monkeypatch):
    from backend.app.knowledge import telemetry
    monkeypatch.setattr(telemetry, "allocate_context_budget", lambda: {"knowledge": 200})
    build_knowledge_context("rag", retriever=lambda _: [{**SOURCE, "content": "x" * 9000},
                                                     {**SOURCE, "path": "omitted.md"}], trace_id="original-trace")
    token = citations.take_receipt()
    rows = citations.recall_sources(token)
    assert len(rows) == 1 and rows[0]["path"] == "docs/rag.md"
    assert rows[0]["origin_trace_id"] == "original-trace"
    assert "content" not in rows[0]
    assert citations.recall_sources("forged") == []
    assert citations.recall_sources("a" * 43) == []


@pytest.mark.parametrize("stream", [False, True])
def test_two_turn_citation_followup_uses_exact_receipt_without_search_or_live_tools(monkeypatch, stream):
    chat = importlib.import_module("backend.app.api.chat")
    context = importlib.import_module("backend.app.memory.context")
    tools = importlib.import_module("backend.app.agents.tools")
    model_calls = []
    searches = []
    events = []
    def retrieve(query):
        searches.append(query)
        return [SOURCE]
    monkeypatch.setattr(context, "retrieve_knowledge", retrieve)
    monkeypatch.setattr(context, "retrieve_memory_context", lambda *a, **kw: [])
    monkeypatch.setattr(context, "format_conversation_context", lambda: "")
    async def no_tool(*a, **kw):
        raise AssertionError("citation followup invoked a live tool")
    monkeypatch.setattr(tools, "execute_tool", no_tool)
    async def publish(event):
        events.append(event)
    monkeypatch.setattr(chat.event_bus, "publish", publish)
    async def answer(**kwargs):
        system = kwargs["messages"][0]["content"]
        model_calls.append(system)
        return {"message": {"content": "Reference answer"}, "done": True}
    async def streaming(**kwargs):
        yield await answer(**kwargs)
    monkeypatch.setattr(chat.model_service.provider, "chat", answer)
    monkeypatch.setattr(chat.model_service.provider, "stream_chat", streaming)
    async def request(message, receipt=None):
        req = chat.ChatRequest(message=message, reference_receipt=receipt, agent_id="system")
        if not stream:
            return await chat.chat(req)
        response = await chat.chat_stream(req)
        rows = [json.loads(line) async for line in response.body_iterator]
        return next(row for row in rows if row["event"] == "model.request_completed")
    async def run():
        first = await request("Using the Open WebUI knowledge base, explain hybrid search. Cite sources.")
        token = first["reference_receipt"]
        assert token
        second = await request(FOLLOWUP, token)
        assert second["reference_receipt"]
        assert len(searches) == 1
        system = model_calls[-1]
        assert "Source: docs/rag.md; chunk: original-1" in system
        assert "PRIOR ANSWER REFERENCE PROVENANCE" in system
        assert "PRIVATE REFERENCE CONTENT" not in system
        assert "without a live tool result" in system
        assert first["trace_id"] in system
        assert token not in json.dumps([e.metadata for e in events])
        await request(FOLLOWUP)
        assert "No retained source metadata" in model_calls[-1]
        assert "original-1" not in model_calls[-1]
        # A receipt alone must not inject references into ordinary conversation.
        build_knowledge_context("Hello", retriever=lambda _: [], reference_receipt=token)
        await flush_knowledge_telemetry()
        assert citations.take_receipt() is None
    asyncio.run(run())


def test_followup_recognition_does_not_capture_new_reference_topics():
    assert citations.is_citation_followup(FOLLOWUP)
    assert citations.is_citation_followup("Sources?")
    assert not citations.is_citation_followup("Using the KB, explain settings that enable RAG. Cite sources.")
    assert not citations.is_citation_followup("What happened last time we inspected Docker? Cite the historical episode and trace IDs.")
