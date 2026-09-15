import re
import socket

from backend.app.agents.registry import get_agent
from backend.app.agents.base import AgentDefinition
from backend.app.memory.short_term import get_conversation_history


SYSTEM_KEYWORDS = {
    "system overview",
    "status report",
    "core status",
    "c.o.r.e. status",
    "cybertron doing",
    "how is cybertron",
    "cpu",
    "memory",
    "ram",
    "disk",
    "process",
    "processes",
    "uptime",
    "system",
    "host",
    "machine",
}

SECURITY_KEYWORDS = {
    "secure",
    "defensive",
    "defense",
    "attack surface",
    "exposure",
    "exposed services",
    "risk posture",
    "security posture",
    "security snapshot",
    "security check",
    "security scan",
    "hardening",
    "suspicious",
    "threat",
    "threats",
}

INFRASTRUCTURE_KEYWORDS = {
    "docker",
    "container",
    "containers",
    "network",
    "interface",
    "interfaces",
    "service",
    "services",
    "port",
    "ports",
    "reachability",
    "reachable",
    "service status",
    "health summary",
    "service health",
    "http://",
    "https://",
    "ollama",
    "open webui",
    "open-webui",
    "searxng",
    "langfuse",
    "kokoro",
    "frontend",
    "backend",
    "core frontend",
    "core backend",
    "incident",
    "incidents",
    "failing",
    "failures",
    "overnight",
    "last hour",
    "past hour",
    "last 24 hours",
    "since midnight",
    "what happened",
    "what failed",
    "today",
    "yesterday",
    "anything go wrong",
    "infrastructure",
    "details for",
    "expose",
}

FOLLOWUP_PATTERNS = (
    r"\b(?:it|its|they|them|their|those|these|that|this)\b",
    r"\b(?:which|what)\s+(?:one|ones)\b",
    r"\bwhat\s+about\b",
    r"\bhow\s+about\b",
    r"\b(?:any|which)\s+(?:of\s+)?(?:them|those|these)\b",
    r"\b(?:unhealthy|healthy|failing|failed|reachable|running|stopped)\b",
)


def _matches_keyword(
    normalized: str,
    keyword: str,
) -> bool:
    if not keyword.isalnum():
        return keyword in normalized

    return (
        re.search(
            rf"\b{re.escape(keyword)}\b",
            normalized,
        )
        is not None
    )


def _mentions_local_host(normalized: str) -> bool:
    """Match the actual local hostname despite speech punctuation/spacing variants."""
    compact_message = re.sub(r"[^a-z0-9]", "", normalized)
    compact_hostname = re.sub(r"[^a-z0-9]", "", socket.gethostname().lower())

    return bool(
        compact_hostname
        and len(compact_hostname) >= 4
        and compact_hostname in compact_message
    )


def _route_explicit(message: str) -> AgentDefinition:
    normalized = message.lower()

    overview_phrases = (
        "system overview",
        "status report",
        "core status",
        "c.o.r.e. status",
        "cybertron doing",
        "how is cybertron",
    )

    if _mentions_local_host(normalized):
        return get_agent("system")

    if any(
        phrase in normalized
        for phrase in overview_phrases
    ):
        return get_agent("system")

    if any(
        _matches_keyword(normalized, keyword)
        for keyword in SECURITY_KEYWORDS
    ):
        return get_agent("security")

    if any(
        _matches_keyword(normalized, keyword)
        for keyword in INFRASTRUCTURE_KEYWORDS
    ):
        return get_agent("infrastructure")

    if any(
        _matches_keyword(normalized, keyword)
        for keyword in SYSTEM_KEYWORDS
    ):
        return get_agent("system")

    return get_agent("general")


def _looks_like_followup(message: str) -> bool:
    normalized = message.lower().strip()
    return any(re.search(pattern, normalized) for pattern in FOLLOWUP_PATTERNS)


def route_agent(message: str) -> AgentDefinition:
    """Route explicit intent first, then inherit prior domain for follow-ups."""
    current = _route_explicit(message)
    if current.id != "general" or not _looks_like_followup(message):
        return current

    history = get_conversation_history()
    if not history:
        return current

    # The latest user prompt is the strongest signal for the active domain.
    # Walk backward so a general conversational turn does not erase a recent
    # systems/infrastructure/security topic.
    for exchange in reversed(history[-4:]):
        previous = _route_explicit(exchange.get("prompt", ""))
        if previous.id != "general":
            return previous

    return current
