import asyncio
from datetime import datetime, timezone

from backend.app.telemetry.alerts import evaluate_alerts
from backend.app.telemetry.incidents import update_incidents
from backend.app.telemetry.store import (
    insert_sample,
    prune,
)
from backend.app.tools.system import system_snapshot
from backend.app.tools.docker import docker_inventory
from backend.app.tools.services import service_status
from backend.app.tools.listeners import listener_inventory


_task: asyncio.Task | None = None


async def collect_sample() -> dict:
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
        if str(container.get("State", "")).lower()
        == "running"
    )

    service_latencies = [
        item["latency_ms"]
        for item in services.get("services", [])
        if isinstance(
            item.get("latency_ms"),
            (int, float),
        )
    ]

    average_latency = (
        sum(service_latencies) / len(service_latencies)
        if service_latencies
        else 0.0
    )

    gpu = system.get("gpu") or {}

    return {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "cpu_percent": system["cpu"]["usage_percent"],
        "memory_percent": system["memory"]["usage_percent"],
        "disk_percent": system["disk"]["usage_percent"],
        "gpu_percent": (
            gpu.get("usage_percent")
            if gpu.get("available")
            else None
        ),
        "docker_running": running_containers,
        "docker_total": docker.get(
            "count",
            len(containers),
        ),
        "services_reachable": services.get(
            "reachable",
            0,
        ),
        "services_total": services.get(
            "total",
            0,
        ),
        "listeners": listeners.get(
            "count",
            len(listeners.get("listeners", [])),
        ),
        "service_latency_ms": round(
            average_latency,
            2,
        ),
    }


async def _sampler_loop() -> None:
    while True:
        try:
            sample = await collect_sample()

            await asyncio.to_thread(
                insert_sample,
                sample,
            )

            alerts = evaluate_alerts(sample)
            update_incidents(alerts)

            await asyncio.to_thread(
                prune,
                7,
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[telemetry] sample failed: {exc}"
            )

        await asyncio.sleep(15)


async def start_sampler() -> None:
    global _task

    if _task and not _task.done():
        return

    try:
        sample = await collect_sample()

        await asyncio.to_thread(
            insert_sample,
            sample,
        )

        alerts = evaluate_alerts(sample)
        update_incidents(alerts)
    except Exception as exc:
        print(
            f"[telemetry] initial sample failed: {exc}"
        )

    _task = asyncio.create_task(
        _sampler_loop()
    )


async def stop_sampler() -> None:
    global _task

    if not _task:
        return

    _task.cancel()

    try:
        await _task
    except asyncio.CancelledError:
        pass

    _task = None
