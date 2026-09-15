import asyncio
import importlib
import json

from backend.app.memory.episodic import EpisodicStore


def test_context_events_report_only_selected_provenance(tmp_path, monkeypatch):
    retrieval = importlib.import_module("backend.app.memory.episodic_retrieval")
    bus = importlib.import_module("backend.app.events.bus")
    store = EpisodicStore(tmp_path / "episodes.db")
    episode = store.record(prompt="Docker secret prompt", outcome="private outcome " * 4000,
                           status="complete", trace_id="old-trace", tool_id="docker.inventory")
    monkeypatch.setattr(retrieval, "episodic_store", store)

    async def scenario():
        events = []
        finished = asyncio.Event()

        async def publish(event):
            events.append(event)
            if event.event_type == "episodic.context_selected":
                finished.set()

        monkeypatch.setattr(bus.event_bus, "publish", publish)
        context = retrieval.build_episodic_context("Docker before?", session_id="session", trace_id="new-trace")
        await asyncio.wait_for(finished.wait(), 2)
        assert [e.event_type for e in events] == ["episodic.search_started", "episodic.search_completed", "episodic.context_selected"]
        assert all(e.trace_id == "new-trace" and e.session_id == "session" for e in events)
        metadata = events[-1].metadata
        assert metadata["selected_count"] == metadata["matched_count"] == 1
        assert metadata["estimated_tokens"] <= metadata["token_budget"]
        assert metadata["episodes"][0]["episode_id"] == episode["id"]
        assert metadata["episodes"][0]["trace_id"] == "old-trace"
        assert metadata["episodes"][0]["summary_truncated"] is True
        assert episode["id"] in context
        assert "private outcome" not in json.dumps(metadata)
        assert "secret prompt" not in json.dumps(metadata)

        events.clear()
        assert retrieval.build_episodic_context("Hello") == ""
        await asyncio.sleep(0)
        assert events == []
        finished.clear()
        assert retrieval.build_episodic_context("unrelated before?", trace_id="empty") == ""
        await asyncio.wait_for(finished.wait(), 2)
        assert events[-1].metadata["selected_count"] == 0
        assert events[-1].metadata["matched_count"] == 0

    asyncio.run(scenario())


def test_selection_excludes_records_that_cannot_fit(tmp_path):
    from backend.app.memory.episodic_retrieval import format_episodic_context
    store = EpisodicStore(tmp_path / "episodes.db")
    episode = store.record(prompt="Docker", outcome="inventory", status="complete")
    selection = []
    assert format_episodic_context([episode], token_budget=1, selection=selection) == ""
    assert selection == []
