import asyncio
import importlib
import json

import pytest

from backend.app.agents.registry import get_agent
from backend.app.agents.tools import select_tool

PROMPT = (
    "Using the Open WebUI knowledge base, explain how hybrid search works in RAG. "
    "Cite the source document or section, and label the answer as reference guidance "
    "rather than a live inspection."
)


@pytest.mark.parametrize("agent_id", ["infrastructure", "system", "security", "general"])
def test_reference_request_never_invokes_implicit_live_tool(agent_id):
    assert select_tool(get_agent(agent_id), PROMPT) == (None, {})


@pytest.mark.parametrize("prompt", [
    "Is Open WebUI reachable?", "Check Open WebUI service status",
    "Check Open WebUI and explain the result using the documentation",
])
def test_live_service_requests_still_use_tools(prompt):
    tool, _ = select_tool(get_agent("infrastructure"), prompt)
    assert tool is not None


@pytest.mark.parametrize("stream", [False, True])
def test_exact_reference_prompt_reaches_model_with_kb_context(tmp_path, monkeypatch, stream):
    chat = importlib.import_module("backend.app.api.chat")
    context = importlib.import_module("backend.app.memory.context")
    retrieval = importlib.import_module("backend.app.knowledge.retrieval")
    agent_tools = importlib.import_module("backend.app.agents.tools")
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    (chunks / "hybrid.json").write_text(json.dumps({
        "kb": "open-webui", "chunk_id": "hybrid-1", "source_path": "docs/rag.md",
        "section": "Hybrid search", "content": "Hybrid search combines keyword and vector retrieval.",
    }))
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"knowledge_bases": [{
        "id": "open-webui", "name": "Open WebUI", "enabled": True,
        "type": "chunk_directory", "path": "chunks", "triggers": ["open webui"],
    }]}))
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    monkeypatch.setattr(context, "retrieve_knowledge", lambda query: retrieval.retrieve_knowledge(query, registry_path=registry))
    monkeypatch.setattr(context, "retrieve_memory_context", lambda *a, **k: [])
    monkeypatch.setattr(context, "format_conversation_context", lambda: "")

    async def no_tool(*a, **k):
        raise AssertionError("Reference prompt invoked a live service tool")

    def check(messages):
        system = messages[0]["content"]
        assert "REFERENCE KNOWLEDGE — NOT LIVE SYSTEM EVIDENCE" in system
        assert "Hybrid search combines keyword and vector retrieval." in system
        assert "Hybrid search" in system

    async def answer(**kwargs):
        check(kwargs["messages"])
        return {"message": {"content": "Reference guidance: hybrid search"}}

    async def streaming(**kwargs):
        yield await answer(**kwargs)

    async def publish(event):
        pass

    monkeypatch.setattr(agent_tools, "execute_tool", no_tool)
    monkeypatch.setattr(chat.event_bus, "publish", publish)
    monkeypatch.setattr(chat.model_service.provider, "chat", answer)
    monkeypatch.setattr(chat.model_service.provider, "stream_chat", streaming)

    async def run():
        request = chat.ChatRequest(message=PROMPT)
        if stream:
            response = await chat.chat_stream(request)
            output = "".join([line async for line in response.body_iterator])
            assert '"event": "tool.result"' not in output
            chat.active_requests.clear()
        else:
            output = json.dumps(await chat.chat(request))
        assert "Reference guidance: hybrid search" in output

    asyncio.run(run())
