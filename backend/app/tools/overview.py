import asyncio

from backend.app.tools.system import system_snapshot
from backend.app.tools.docker import docker_inventory
from backend.app.tools.services import service_status
from backend.app.tools.listeners import listener_inventory


async def system_overview() -> dict:
    (
        system,
        docker,
        services,
        listeners,
    ) = await asyncio.gather(
        system_snapshot(),
        docker_inventory(),
        service_status(),
        listener_inventory(),
    )

    containers = docker.get("containers") or []

    running_containers = sum(
        1
        for container in containers
        if str(
            container.get("State", "")
        ).lower() == "running"
    )

    return {
        "system": system,
        "docker": {
            "available": docker.get(
                "available",
                False,
            ),
            "total": docker.get(
                "count",
                len(containers),
            ),
            "running": running_containers,
        },
        "services": {
            "total": services.get("total", 0),
            "reachable": services.get(
                "reachable",
                0,
            ),
            "unreachable": services.get(
                "unreachable",
                0,
            ),
        },
        "network": {
            "listeners": listeners.get(
                "count",
                len(
                    listeners.get(
                        "listeners",
                        [],
                    )
                ),
            ),
        },
    }
