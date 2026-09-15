from backend.app.memory.episode_capture import capture_episode, should_capture_episode
from backend.app.memory.episodic import EpisodicStore


def test_general_conversation_is_not_captured():
    assert should_capture_episode(agent_id="general", tool_id=None, status="complete") is False


def test_tool_backed_work_is_captured():
    assert should_capture_episode(agent_id="infrastructure", tool_id="docker.inventory", status="complete") is True


def test_failures_are_captured_even_for_general_agent():
    assert should_capture_episode(agent_id="general", tool_id=None, status="failed") is True


def test_capture_preserves_trace_and_tool_provenance(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.db")
    episode = capture_episode(
        prompt="Show Docker containers",
        outcome="11 containers running",
        status="complete",
        session_id="session-1",
        trace_id="trace-1",
        agent_id="infrastructure",
        tool_id="docker.inventory",
        metadata={"verified": True},
        store=store,
    )
    assert episode is not None
    assert episode["trace_id"] == "trace-1"
    assert episode["tool_id"] == "docker.inventory"
    assert episode["importance"] == 7
    assert "tool" in episode["tags"]


def test_failed_episode_gets_high_salience_inputs(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.db")
    episode = capture_episode(
        prompt="Check service",
        outcome="connection refused",
        status="failed",
        session_id="session-2",
        trace_id="trace-2",
        agent_id="general",
        store=store,
    )
    assert episode is not None
    assert episode["importance"] == 8
    assert episode["pain_score"] == 9
    assert "failure" in episode["tags"]
