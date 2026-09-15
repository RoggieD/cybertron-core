import asyncio
import importlib
import json
import httpx
from fastapi import FastAPI

chat = importlib.import_module("backend.app.api.chat")


def test_stream_terminal_states(monkeypatch):
    async def scenario(cancel=False, fail=False, explicit=False):
        events = []
        closed = []
        waiting = asyncio.Event()
        accepted = asyncio.Event()
        tokens = []

        async def publish(event):
            events.append(event.event_type)

        async def tool(*args):
            return None, None

        async def provider(**kwargs):
            try:
                if fail:
                    raise RuntimeError("test failure")
                if cancel:
                    waiting.set()
                    await asyncio.Event().wait()
                yield {"message": {"content": "ok"}, "done": True}
            finally:
                closed.append(True)

        monkeypatch.setattr(chat.event_bus, "publish", publish)
        monkeypatch.setattr(chat, "run_agent_tool", tool)
        monkeypatch.setattr(chat, "build_messages", lambda *a, **kw: [])
        monkeypatch.setattr(chat.model_service.provider, "stream_chat", provider)
        response = await chat.chat_stream(chat.ChatRequest(message="hello", agent_id="general"))

        async def consume():
            async for line in response.body_iterator:
                event = json.loads(line)
                if event["event"] == "request.accepted":
                    tokens.append(event["cancel_token"])
                    accepted.set()

        task = asyncio.create_task(consume())
        if cancel:
            await waiting.wait()
            if explicit:
                await accepted.wait()
                # Keep consuming the stream: cancellation must not depend on disconnect.
                app = FastAPI()
                app.include_router(chat.router)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    rejected = await client.post("/api/chat/cancel", json={"token": "unknown"})
                    assert rejected.status_code == 404
                    reply = await client.post("/api/chat/cancel", json={"token": tokens[0]})
                    assert reply.status_code == 200
                    result = reply.json()
                assert result == {"status": "cancelled"}
                assert closed == [True]
                await task
                assert await chat.cancel_request(chat.CancelRequest(token=tokens[0])) == result
            else:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        else:
            await task
        expected = "request.cancelled" if cancel else "request.failed" if fail else "request.completed"
        assert [e for e in events if e.startswith("request.")] == [expected]
        assert closed == [True]
        chat.active_requests.clear()

    asyncio.run(scenario())
    asyncio.run(scenario(fail=True))
    asyncio.run(scenario(cancel=True))
    asyncio.run(scenario(cancel=True, explicit=True))
