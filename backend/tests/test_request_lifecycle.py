import asyncio
import importlib
import json

chat = importlib.import_module("backend.app.api.chat")


def test_stream_terminal_states(monkeypatch):
    async def scenario(cancel=False, fail=False):
        events = []
        closed = []
        waiting = asyncio.Event()

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
                json.loads(line)

        task = asyncio.create_task(consume())
        if cancel:
            await waiting.wait()
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

    asyncio.run(scenario())
    asyncio.run(scenario(fail=True))
    asyncio.run(scenario(cancel=True))
