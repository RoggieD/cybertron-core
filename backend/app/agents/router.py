import re
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
    "infrastructure",
    "details for",
    "expose",
}


def _matches_keyword(
    normalized: str,
    keyword: str,
) -> bool:
    # Phrases, URLs, and punctuation-bearing aliases are
    # intentionally matched as substrings.
    if not keyword.isalnum():
        return keyword in normalized

    # Single words must match whole words so, for example,
    # "port" does not accidentally match "report".
    return (
        re.search(
            rf"\b{re.escape(keyword)}\b",
            normalized,
        )
        is not None
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

    if any(
        phrase in normalized
        for phrase in overview_phrases
    ):
        return get_agent("system")

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
