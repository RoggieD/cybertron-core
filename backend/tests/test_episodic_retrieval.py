import importlib
from datetime import datetime, timezone

import pytest

from backend.app.memory.episodic import EpisodicStore
from backend.app.memory.episodic_retrieval import retrieve_episodic_context, format_episodic_context
from backend.app.memory.context_budget import estimate_tokens
from backend.app.memory.short_term import set_conversation_history, reset_conversation_history

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return EpisodicStore(tmp_path / "episodes.db")


def record(store, **kwargs):
    fields = dict(prompt="Docker timeout", outcome="Restart restored Docker", status="complete",
                  trace_id="trace-old", tool_id="docker.inventory", timestamp=NOW.isoformat())
    fields.update(kwargs)
    return store.record(**fields)


@pytest.mark.parametrize("message", ["Hello", "Explain Docker", "Docker timeout", "Have we seen this before?"])
def test_no_unrequested_or_subjectless_history(store, message):
    record(store)
    assert retrieve_episodic_context(message, store=store) == []


def test_relevance_gate_beats_unrelated_salience(store):
    expected = record(store, timestamp="2020-01-01T00:00:00Z")
    record(store, prompt="network outage", outcome="network repaired", tool_id="network",
           importance=10, pain_score=10, recurrence_count=100)
    assert retrieve_episodic_context("What fixed Docker timeout previously?", store=store, now=NOW) == [expected]


@pytest.mark.parametrize("field,value", [("importance", 10), ("pain_score", 10),
                                         ("recurrence_count", 3), ("timestamp", NOW.isoformat())])
def test_salience_orders_equally_relevant_matches(store, field, value):
    baseline = dict(importance=5, pain_score=5, recurrence_count=1, timestamp="2026-09-10T00:00:00Z")
    record(store, outcome="Docker timeout alpha", **baseline)
    baseline[field] = value
    expected = record(store, outcome="Docker timeout beta", **baseline)
    assert retrieve_episodic_context("Docker timeout before?", store=store, now=NOW)[0] == expected


@pytest.mark.parametrize("message", ["Have we seen this before?", "What happened last time?", "What fixed this previously?"])
def test_followup_uses_user_subject(store, message):
    expected = record(store)
    token = set_conversation_history([{"prompt": "Docker timeout", "response": "network speculation"}])
    try:
        assert retrieve_episodic_context(message, store=store) == [expected]
    finally:
        reset_conversation_history(token)


def test_excludes_current_trace_and_handles_zero_limit(store):
    record(store)
    assert retrieve_episodic_context("Docker before?", store=store, trace_id="trace-old") == []
    assert retrieve_episodic_context("Docker before?", store=store, limit=0) == []


@pytest.mark.parametrize("message", ["Have we seen this before?", "What happened last time?", "What fixed this previously?"])
def test_docker_recall_reaches_model_context(message):
    from backend.app.tools.renderers import should_return_verified_only
    assert not should_return_verified_only(message, "docker.inventory")


def test_search_reaches_beyond_recent_window(store):
    expected = record(store, timestamp="2020-01-01T00:00:00Z")
    for index in range(251):
        record(store, prompt="unrelated", outcome=f"other {index}", tool_id="other")
    assert retrieve_episodic_context("Docker timeout before?", store=store) == [expected]


def test_whole_records_preserve_warning_and_provenance(store):
    episode = record(store, metadata={"previous_trace_id": "trace-earlier"})
    text = format_episodic_context([episode], token_budget=500)
    assert "HISTORICAL OPERATIONAL MEMORY" in text
    assert "NOT CURRENT/LIVE EVIDENCE" in text
    assert all(value in text for value in [episode["id"], "trace-old", "trace-earlier"])
    assert estimate_tokens(text) <= 500
    assert format_episodic_context([episode], token_budget=10) == ""
    assert format_episodic_context([episode], token_budget=0) == ""
    oversized = dict(episode, outcome="x" * 10000)
    assert format_episodic_context([oversized, episode], token_budget=500) == text


def test_build_messages_integrates_history_and_keeps_live_rules(store, monkeypatch):
    context = importlib.import_module("backend.app.memory.context")
    retrieval = importlib.import_module("backend.app.memory.episodic_retrieval")
    chat = importlib.import_module("backend.app.api.chat")
    episode = record(store)
    monkeypatch.setattr(retrieval, "episodic_store", store)
    monkeypatch.setattr(context, "retrieve_memory_context", lambda *a, **k: [])
    monkeypatch.setattr(context, "retrieve_knowledge", lambda *a, **k: [])
    monkeypatch.setattr(context, "format_conversation_context", lambda: "")
    messages = chat.build_messages("Docker timeout before?", "test", "test", "test")
    system = messages[0]["content"]
    assert episode["id"] in system
    assert "Only tool results supplied in THIS request" in system
    assert "NOT CURRENT/LIVE EVIDENCE" in system
    monkeypatch.setattr(chat, "format_tool_context", lambda *a: "LIVE TOOL: healthy now")
    with_tool = chat.build_messages("Docker timeout before?", "test", "test", "test", "docker.inventory", {})
    assert "LIVE TOOL: healthy now" in with_tool[0]["content"]
    assert episode["id"] in with_tool[0]["content"]
