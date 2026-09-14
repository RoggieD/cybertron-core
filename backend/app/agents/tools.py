from backend.app.agents.base import AgentDefinition
from backend.app.tools.registry import execute_tool


def select_tool(
    agent: AgentDefinition,
    message: str,
) -> str | None:
    normalized = message.lower()

    if agent.id == "system":
        process_terms = (
            "process",
            "processes",
            "running processes",
            "top processes",
        )

        if any(term in normalized for term in process_terms):
            return "system.processes"

        return "system.snapshot"

    if agent.id == "infrastructure":
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
            return "network.interfaces"

        return "docker.inventory"

    return None


async def run_agent_tool(
    agent: AgentDefinition,
    message: str,
) -> tuple[str | None, dict | None]:
    tool_id = select_tool(
        agent,
        message,
    )

    if tool_id is None:
        return None, None

    result = await execute_tool(tool_id)

    return tool_id, result
