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
