import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app import main


def test_app_starts_sampler_before_serving_and_stops_on_exit(monkeypatch):
    calls = []

    async def start():
        calls.append("start")

    async def stop():
        calls.append("stop")

    monkeypatch.setattr(main, "start_sampler", start)
    monkeypatch.setattr(main, "stop_sampler", stop)
    with TestClient(main.app) as client:
        assert calls == ["start"]
        assert client.get("/").json()["status"] == "online"
        assert calls == ["start"]
    assert calls == ["start", "stop"]


@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError])
def test_lifespan_cleans_up_when_context_exits_abnormally(monkeypatch, error):
    start, stop = AsyncMock(), AsyncMock()
    monkeypatch.setattr(main, "start_sampler", start)
    monkeypatch.setattr(main, "stop_sampler", stop)

    async def run():
        with pytest.raises(error):
            async with main.lifespan(main.app):
                start.assert_awaited_once()
                stop.assert_not_awaited()
                raise error()
        stop.assert_awaited_once()

    asyncio.run(run())


def test_startup_failure_is_propagated_before_serving(monkeypatch):
    start = AsyncMock(side_effect=RuntimeError("startup failed"))
    stop = AsyncMock()
    monkeypatch.setattr(main, "start_sampler", start)
    monkeypatch.setattr(main, "stop_sampler", stop)
    with pytest.raises(RuntimeError, match="startup failed"):
        with TestClient(main.app):
            pytest.fail("Application started despite initialization failure")
    start.assert_awaited_once()
    stop.assert_not_awaited()
