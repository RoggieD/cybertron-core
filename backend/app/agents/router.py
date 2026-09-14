import re
import socket

from backend.app.agents.registry import get_agent
from backend.app.agents.base import AgentDefinition


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
    "security",
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


def route_agent(message: str) -> AgentDefinition:
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
