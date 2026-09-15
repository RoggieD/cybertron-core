from backend.app.memory.episodic import EpisodicStore


def test_record_and_retrieve_episode(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.db")
    episode = store.record(
        prompt="Why did Ollama stop responding?",
        outcome="Restarted the Ollama service and health checks recovered.",
        status="resolved",
        session_id="session-1",
        trace_id="trace-1",
        agent_id="infrastructure",
        tool_id="service.status",
        importance=8,
        pain_score=7,
        tags=["Ollama", "Service"],
        metadata={"verified": True},
    )

    loaded = store.get(episode["id"])
    assert loaded is not None
    assert loaded["trace_id"] == "trace-1"
    assert loaded["agent_id"] == "infrastructure"
    assert loaded["tool_id"] == "service.status"
    assert loaded["status"] == "resolved"
    assert loaded["importance"] == 8
    assert loaded["pain_score"] == 7
    assert loaded["tags"] == ["ollama", "service"]
    assert loaded["metadata"]["verified"] is True


def test_recent_returns_newest_first(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.db")
    store.record(prompt="first", outcome="one", status="complete", timestamp="2026-09-15T10:00:00+00:00")
    store.record(prompt="second", outcome="two", status="complete", timestamp="2026-09-15T11:00:00+00:00")

    assert [item["prompt"] for item in store.recent()] == ["second", "first"]


def test_scores_are_bounded(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.db")
    episode = store.record(
        prompt="bounded",
        outcome="bounded",
        status="complete",
        importance=99,
        pain_score=-5,
        recurrence_count=0,
    )
    assert episode["importance"] == 10
    assert episode["pain_score"] == 0
    assert episode["recurrence_count"] == 1


def test_identical_operational_outcome_consolidates(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.db")
    first = store.record(
        prompt="Operational tool execution: docker.inventory",
        outcome="Docker inventory completed: 14 total; 11 running.",
        status="complete",
        session_id="session-1",
        trace_id="trace-1",
        agent_id="infrastructure",
        tool_id="docker.inventory",
    )
    second = store.record(
        prompt="Operational tool execution: docker.inventory",
        outcome="Docker inventory completed: 14 total; 11 running.",
        status="complete",
        session_id="session-2",
        trace_id="trace-2",
        agent_id="infrastructure",
        tool_id="docker.inventory",
    )

    assert second["id"] == first["id"]
    assert second["recurrence_count"] == 2
    assert second["trace_id"] == "trace-2"
    assert second["metadata"]["previous_trace_id"] == "trace-1"
    assert len(store.recent()) == 1
