from backend.app.agents.router import route_agent
from backend.app.memory.short_term import (
    reset_conversation_history,
    set_conversation_history,
)


def _history(prompt: str, response: str = "Verified result"):
    return [{"prompt": prompt, "response": response}]


def test_followup_inherits_infrastructure_domain():
    token = set_conversation_history(
        _history("Show me the Docker containers running on this host.")
    )
    try:
        assert route_agent("Which of those are unhealthy?").id == "infrastructure"
    finally:
        reset_conversation_history(token)


def test_followup_inherits_security_domain():
    token = set_conversation_history(
        _history("Give me a security posture snapshot.")
    )
    try:
        assert route_agent("What about those findings?").id == "security"
    finally:
        reset_conversation_history(token)


def test_explicit_new_intent_overrides_prior_domain():
    token = set_conversation_history(
        _history("Show me the Docker containers running on this host.")
    )
    try:
        assert route_agent("What is the system uptime?").id == "system"
    finally:
        reset_conversation_history(token)


def test_general_followup_without_history_stays_general():
    token = set_conversation_history([])
    try:
        assert route_agent("Which of those are unhealthy?").id == "general"
    finally:
        reset_conversation_history(token)
