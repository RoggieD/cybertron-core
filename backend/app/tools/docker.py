import asyncio
import json
import shutil
import subprocess


def _docker_inventory_sync() -> dict:
    docker = shutil.which("docker")

    if not docker:
        return {
            "available": False,
            "error": "Docker CLI not found.",
            "containers": [],
        }

    command = [
        docker,
        "ps",
        "--all",
        "--format",
        "{{json .}}",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    if result.returncode != 0:
        return {
            "available": False,
            "error": result.stderr.strip(),
            "containers": [],
        }

    containers = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if line:
            containers.append(json.loads(line))

    return {
        "available": True,
        "count": len(containers),
        "containers": containers,
    }


async def docker_inventory() -> dict:
    return await asyncio.to_thread(
        _docker_inventory_sync
    )


async def docker_health_summary() -> dict:
    inventory = await docker_inventory()
    if not inventory.get("available"):
        return inventory

    healthy = []
    unhealthy = []
    running_unspecified = []
    stopped = []

    for container in inventory.get("containers", []):
        status = str(container.get("Status", ""))
        status_lower = status.lower()
        item = {
            "name": container.get("Names", "unknown"),
            "status": status or "unknown",
            "image": container.get("Image", "unknown"),
        }

        if status_lower.startswith("up"):
            if "(unhealthy)" in status_lower:
                unhealthy.append(item)
            elif "(healthy)" in status_lower:
                healthy.append(item)
            else:
                running_unspecified.append(item)
        else:
            stopped.append(item)

    return {
        "available": True,
        "total": len(inventory.get("containers", [])),
        "healthy": healthy,
        "unhealthy": unhealthy,
        "running_unspecified": running_unspecified,
        "stopped": stopped,
    }


async def docker_inspect(container_name: str) -> dict:
    import asyncio
    import json
    import shutil
    import subprocess

    def _inspect_sync() -> dict:
        docker = shutil.which("docker")

        if not docker:
            return {
                "available": False,
                "found": False,
                "container": container_name,
                "error": "Docker CLI not found.",
            }

        result = subprocess.run(
            [
                docker,
                "inspect",
                container_name,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            return {
                "available": True,
                "found": False,
                "container": container_name,
                "error": result.stderr.strip(),
            }

        data = json.loads(result.stdout)

        if not data:
            return {
                "available": True,
                "found": False,
                "container": container_name,
            }

        item = data[0]

        state = item.get("State", {})
        config = item.get("Config", {})
        network = item.get("NetworkSettings", {})

        return {
            "available": True,
            "found": True,
            "container": container_name,
            "id": item.get("Id"),
            "name": item.get("Name", "").lstrip("/"),
            "image": config.get("Image"),
            "status": state.get("Status"),
            "running": state.get("Running"),
            "health": (
                state.get("Health", {}).get("Status")
                if state.get("Health")
                else None
            ),
            "started_at": state.get("StartedAt"),
            "finished_at": state.get("FinishedAt"),
            "restart_count": item.get("RestartCount"),
            "ports": network.get("Ports") or {},
            "networks": list(
                (network.get("Networks") or {}).keys()
            ),
        }

    return await asyncio.to_thread(_inspect_sync)
