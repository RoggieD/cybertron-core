import asyncio
import time

import psutil


def _process_inventory_sync() -> dict:
    tracked = []

    for process in psutil.process_iter(
        [
            "pid",
            "name",
            "username",
            "memory_percent",
            "status",
        ]
    ):
        try:
            process.cpu_percent(None)
            tracked.append(process)
        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
        ):
            continue

    # Short sampling interval for meaningful per-process CPU values.
    time.sleep(0.25)

    processes = []

    for process in tracked:
        try:
            info = process.as_dict(
                attrs=[
                    "pid",
                    "name",
                    "username",
                    "memory_percent",
                    "status",
                ]
            )

            processes.append(
                {
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "username": info.get("username"),
                    "cpu_percent": round(
                        process.cpu_percent(None),
                        2,
                    ),
                    "memory_percent": round(
                        info.get("memory_percent") or 0.0,
                        2,
                    ),
                    "status": info.get("status"),
                }
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
        ):
            continue

    processes.sort(
        key=lambda item: (
            item["cpu_percent"],
            item["memory_percent"],
        ),
        reverse=True,
    )

    return {
        "count": len(processes),
        "processes": processes[:25],
        "returned": min(len(processes), 25),
    }


async def process_inventory() -> dict:
    return await asyncio.to_thread(
        _process_inventory_sync
    )
