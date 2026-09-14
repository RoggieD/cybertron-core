from backend.app.agents.base import AgentDefinition
from backend.app.tools.registry import execute_tool


AGENT_TOOL_MAP = {
    "system": "system.snapshot",
    "infrastructure": "docker.inventory",
}


def tool_for_agent(
    agent: AgentDefinition,
) -> str | None:
    return AGENT_TOOL_MAP.get(agent.id)


async def run_agent_tool(
    agent: AgentDefinition,
) -> tuple[str | None, dict | None]:
    tool_id = tool_for_agent(agent)

    if tool_id is None:
        return None, None

    result = await execute_tool(tool_id)

    return tool_id, result
