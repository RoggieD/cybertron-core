import asyncio
import importlib
import json

import pytest

from backend.app.tools.renderers import should_return_verified_only

chat = importlib.import_module("backend.app.api.chat")
PROMPT = "Inspect local Docker containers. Report which are running, stopped, or unhealthy using verified tool results."


@pytest.mark.parametrize("message", [PROMPT, "List Docker containers", "Which containers are unhealthy?", "Show container status"])
def test_inventory_is_direct(message):
    assert should_return_verified_only(message, "docker.inventory")


@pytest.mark.parametrize("message", ["Explain why Docker containers are unhealthy", "Inspect Docker and recommend fixes", "Analyze container status", "How can I fix this container?"])
def test_interpretation_keeps_model(message):
    assert not should_return_verified_only(message, "docker.inventory")


def test_stream_emits_one_verified_report_without_model(monkeypatch):
    async def scenario():
        events = []
        async def publish(event):
            events.append(event.event_type)
        async def tool(*args):
            return "docker.inventory", {"containers": []}
        def no_model(*args, **kwargs):
            raise AssertionError("Inventory must not invoke model")
        monkeypatch.setattr(chat.event_bus, "publish", publish)
        monkeypatch.setattr(chat, "run_agent_tool", tool)
        monkeypatch.setattr(chat.model_service.provider, "stream_chat", no_model)
        response = await chat.chat_stream(chat.ChatRequest(message=PROMPT, agent_id="infrastructure"))
        lines = [json.loads(line) async for line in response.body_iterator]
        reports = [line for line in lines if line["event"] == "tool.result"]
        assert len(reports) == 1
        assert "DOCKER INVENTORY" in reports[0]["content"]
        assert "ANALYSIS" not in reports[0]["content"]
        assert "model.request_started" not in events
        assert events.count("request.completed") == 1
        chat.active_requests.clear()
    asyncio.run(scenario())
