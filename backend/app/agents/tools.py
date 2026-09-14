import re

from backend.app.agents.base import AgentDefinition
from backend.app.tools.registry import execute_tool


def extract_port(message: str) -> int | None:
    match = re.search(
        r"\bport\s+(\d{1,5})\b",
        message.lower(),
    )

    if not match:
        return None

    port = int(match.group(1))

    if 1 <= port <= 65535:
        return port

    return None


def select_tool(
    agent: AgentDefinition,
    message: str,
) -> tuple[str | None, dict]:
    normalized = message.lower()

    if agent.id == "system":
        process_terms = (
            "process",
            "processes",
            "running processes",
            "top processes",
        )

        if any(term in normalized for term in process_terms):
            return "system.processes", {}

        return "system.snapshot", {}

    if agent.id == "infrastructure":
        container_name = extract_container_name(
            message
        )

        if container_name is not None:
            return "docker.inspect", {
                "container_name": container_name,
            }

        url = extract_url(message)

        if url is not None:
            return "network.reachability", {
                "target": url,
            }

        port = extract_port(message)

        if (
            port is not None
            and any(
                term in normalized
                for term in (
                    "reachable",
                    "reachability",
                    "connect",
                    "connectivity",
                )
            )
        ):
            return "network.reachability", {
                "host": "localhost",
                "port": port,
            }

        if port is not None:
            return "network.port_owner", {
                "port": port,
            }

        listener_terms = (
            "listening port",
            "listening ports",
            "listeners",
            "open port",
            "open ports",
            "what ports",
            "services listening",
        )

        if any(term in normalized for term in listener_terms):
            return "network.listeners", {}

        network_terms = (
            "network",
            "interface",
            "interfaces",
            "ip address",
            "ip addresses",
            "ethernet",
            "adapter",
            "adapters",
        )

        if any(term in normalized for term in network_terms):
            return "network.interfaces", {}

        return "docker.inventory", {}

    return None, {}


async def run_agent_tool(
    agent: AgentDefinition,
    message: str,
) -> tuple[str | None, dict | None]:
    tool_id, kwargs = select_tool(
        agent,
        message,
    )

    if tool_id is None:
        return None, None

    result = await execute_tool(
        tool_id,
        **kwargs,
    )

    return tool_id, result


def extract_container_name(
    message: str,
) -> str | None:
    normalized = message.strip()

    patterns = (
        r"\bcontainer\s+([A-Za-z0-9_.-]+)\b",
        r"\bdetails\s+for\s+([A-Za-z0-9_.-]+)\b",
        r"\bdoes\s+([A-Za-z0-9_.-]+)\s+expose\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def extract_url(message: str) -> str | None:
    match = re.search(
        r"https?://[^\s]+",
        message,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(0).rstrip(".,);]}")
