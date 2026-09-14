from backend.app.tools.memory import (
    memory_read,
    memory_search,
)
from backend.app.tools.incidents import incident_summary
from backend.app.tools.overview import system_overview
from backend.app.tools.services import service_status
from backend.app.tools.reachability import network_reachability
from backend.app.tools.base import ToolDefinition
from backend.app.tools.docker import docker_inventory, docker_inspect
from backend.app.tools.system import system_snapshot
from backend.app.tools.processes import process_inventory
from backend.app.tools.network import network_interfaces
from backend.app.tools.listeners import listener_inventory, port_owner
from backend.app.tools.security import security_snapshot


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
    "security.snapshot": ToolDefinition(
        id="security.snapshot",
        name="Defensive Posture Snapshot",
        description=(
            "Read-only local defensive posture assessment using verified "
            "listener, process, and host telemetry."
        ),
        permission_level=0,
        read_only=True,
        handler=security_snapshot,
    ),
    "network.port_owner": ToolDefinition(
        id="network.port_owner",
        name="Port Owner",
        description=(
            "Read-only lookup of listeners bound to a specific TCP/IP port."
        ),
        permission_level=0,
        read_only=True,
        handler=port_owner,
    ),
    "incident.summary": ToolDefinition(
        id="incident.summary",
        name="Incident Summary",
        description=(
            "Read-only summary of persisted incident history "
            "and operational incident analytics."
        ),
        permission_level=0,
        read_only=True,
        handler=incident_summary,
    ),
    "memory.search": ToolDefinition(
        id="memory.search",
        name="Memory Search",
        description=(
            "Search persistent C.O.R.E. memory. "
            "Agent-facing access is read-only and "
            "restricted to system/shared scopes."
        ),
        permission_level=0,
        read_only=True,
        handler=memory_search,
    ),

    "memory.read": ToolDefinition(
        id="memory.read",
        name="Memory Read",
        description=(
            "Read one persistent C.O.R.E. memory "
            "record by ID when policy permits."
        ),
        permission_level=0,
        read_only=True,
        handler=memory_read,
    ),

    "system.overview": ToolDefinition(
        id="system.overview",
        name="System Overview",
        description=(
            "Read-only consolidated system, Docker, "
            "service, and network status."
        ),
        permission_level=0,
        read_only=True,
        handler=system_overview,
    ),
    "service.status": ToolDefinition(
        id="service.status",
        name="Service Status",
        description=(
            "Read-only health summary of known services."
        ),
        permission_level=0,
        read_only=True,
        handler=service_status,
    ),
    "network.reachability": ToolDefinition(
        id="network.reachability",
        name="Network Reachability",
        description=(
            "Read-only HTTP and TCP reachability testing."
        ),
        permission_level=0,
        read_only=True,
        handler=network_reachability,
    ),
    "network.listeners": ToolDefinition(
        id="network.listeners",
        name="Network Listeners",
        description=(
            "Read-only inventory of listening TCP/IP sockets "
            "and owning processes."
        ),
        permission_level=0,
        read_only=True,
        handler=listener_inventory,
    ),
    "network.interfaces": ToolDefinition(
        id="network.interfaces",
        name="Network Interfaces",
        description="Read-only network interface inventory.",
        permission_level=0,
        read_only=True,
        handler=network_interfaces,
    ),
    "docker.inspect": ToolDefinition(
        id="docker.inspect",
        name="Docker Inspect",
        description=(
            "Read-only inspection of a specific Docker container."
        ),
        permission_level=0,
        read_only=True,
        handler=docker_inspect,
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


async def execute_tool(
    tool_id: str,
    **kwargs,
) -> dict:
    tool = get_tool(tool_id)

    if tool.permission_level > 1:
        raise PermissionError(
            f"Tool {tool.id} requires authorization."
        )

    return await tool.handler(**kwargs)
