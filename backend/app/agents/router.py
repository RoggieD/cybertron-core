from backend.app.agents.registry import get_agent
from backend.app.agents.base import AgentDefinition


SYSTEM_KEYWORDS = {
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
    "infrastructure",
    "details for",
    "expose",
}


def route_agent(message: str) -> AgentDefinition:
    normalized = message.lower()

    if any(
        keyword in normalized
        for keyword in INFRASTRUCTURE_KEYWORDS
    ):
        return get_agent("infrastructure")

    if any(
        keyword in normalized
        for keyword in SYSTEM_KEYWORDS
    ):
        return get_agent("system")

    return get_agent("general")
