from backend.app.events.schema import CoreEvent
from backend.app.memory.episode_events import episode_from_event


def test_tool_completed_becomes_verified_episode():
    event = CoreEvent(
        event_type="tool.completed",
        session_id="session-1",
        trace_id="trace-1",
        actor={"type": "tool", "id": "docker.inventory"},
        target={"type": "agent", "id": "infrastructure"},
        status="complete",
        metadata={"result": {"running": 11}},
    )
    episode = episode_from_event(event)
    assert episode is not None
    assert episode["tool_id"] == "docker.inventory"
    assert episode["agent_id"] == "infrastructure"
    assert episode["metadata"]["verified"] is True
    assert '"running": 11' in episode["outcome"]


def test_docker_inventory_is_compact_summary():
    event = CoreEvent(
        event_type="tool.completed",
        actor={"type": "tool", "id": "docker.inventory"},
        target={"type": "agent", "id": "infrastructure"},
        metadata={"result": {"containers": [
            {"State": "running", "HealthStatus": "healthy", "Labels": "x" * 5000},
            {"State": "running", "HealthStatus": "none"},
            {"State": "exited", "HealthStatus": "none"},
        ]}},
    )
    episode = episode_from_event(event)
    assert episode is not None
    assert episode["outcome"] == (
        "Docker inventory completed: 3 total; 2 running; 1 healthy; "
        "1 running without explicit health status; 1 stopped/exited."
    )
    assert "Labels" not in episode["outcome"]


def test_model_error_becomes_failed_episode():
    event = CoreEvent(
        event_type="model.error",
        session_id="session-2",
        trace_id="trace-2",
        actor={"type": "model", "id": "qwen"},
        status="error",
        metadata={"error": "connection refused"},
    )
    episode = episode_from_event(event)
    assert episode is not None
    assert episode["status"] == "failed"
    assert episode["outcome"] == "connection refused"


def test_non_terminal_noise_is_not_an_episode():
    assert episode_from_event(CoreEvent(event_type="model.token")) is None
