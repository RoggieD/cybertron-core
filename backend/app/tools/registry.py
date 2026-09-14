from backend.app.tools.base import ToolDefinition
from backend.app.tools.docker import docker_inventory
from backend.app.tools.system import system_snapshot
from backend.app.tools.processes import process_inventory
from backend.app.tools.network import network_interfaces


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
    "system.processes": ToolDefinition(
        id="system.processes",
        name="Process Inventory",
        description="Read-only process inventory.",
        permission_level=0,
        read_only=True,
        handler=process_inventory,
    ),
    "network.interfaces": ToolDefinition(
        id="network.interfaces",
        name="Network Interfaces",
        description="Read-only network interface inventory.",
        permission_level=0,
        read_only=True,
        handler=network_interfaces,
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
