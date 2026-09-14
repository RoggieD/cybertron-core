from backend.app.tools.base import ToolDefinition
from backend.app.tools.docker import docker_inventory
from backend.app.tools.system import system_snapshot


TOOLS = {
    "system.snapshot": ToolDefinition(
        id="system.snapshot",
        name="System Snapshot",
        description=(
            "Read-only local CPU, memory, disk, "
            "load and uptime inspection."
        ),
        permission_level=0,
        read_only=True,
        handler=system_snapshot,
    ),
    "docker.inventory": ToolDefinition(
        id="docker.inventory",
        name="Docker Inventory",
        description=(
            "Read-only inventory of Docker containers."
        ),
        permission_level=0,
        read_only=True,
        handler=docker_inventory,
    ),
}


def get_tool(tool_id: str) -> ToolDefinition:
    return TOOLS[tool_id]


async def execute_tool(tool_id: str) -> dict:
    tool = get_tool(tool_id)

    if tool.permission_level > 1:
        raise PermissionError(
            f"Tool {tool.id} requires authorization."
        )

    return await tool.handler()
