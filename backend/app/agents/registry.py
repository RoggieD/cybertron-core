from backend.app.agents.base import AgentDefinition


AGENTS = {
    "general": AgentDefinition(
        id="general",
        name="General Agent",
        description="Handles general conversation and ordinary requests.",
        instructions=(
            "Handle general conversation and ordinary user requests. "
            "Do not invent system facts or infrastructure details."
        ),
    ),
    "system": AgentDefinition(
        id="system",
        name="System Agent",
        description="Handles local host inspection and operating-system questions.",
        instructions=(
            "Handle requests about the local machine, operating system, "
            "CPU, memory, disk, processes, uptime, and host status. "
            "Use only verified system information when tools are available."
        ),
    ),
    "infrastructure": AgentDefinition(
        id="infrastructure",
        name="Infrastructure Agent",
        description="Handles Docker, networking, services, and infrastructure health.",
        instructions=(
            "Handle requests about Docker, containers, network interfaces, "
            "services, reachability, and infrastructure health. "
            "Do not claim infrastructure facts unless verified."
        ),
    ),
}


def get_agent(agent_id: str) -> AgentDefinition:
    return AGENTS[agent_id]


def list_agents() -> list[AgentDefinition]:
    return list(AGENTS.values())
