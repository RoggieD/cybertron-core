import os
import platform
import time

import psutil


async def system_snapshot() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    uptime_seconds = int(
        time.time() - psutil.boot_time()
    )

    try:
        load_1, load_5, load_15 = os.getloadavg()
    except OSError:
        load_1 = load_5 = load_15 = None

    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "cpu": {
            "logical_cores": psutil.cpu_count(),
            "physical_cores": psutil.cpu_count(
                logical=False
            ),
            "usage_percent": psutil.cpu_percent(
                interval=0.25
            ),
            "load_average": {
                "1m": load_1,
                "5m": load_5,
                "15m": load_15,
            },
        },
        "memory": {
            "total_bytes": memory.total,
            "available_bytes": memory.available,
            "used_bytes": memory.used,
            "usage_percent": memory.percent,
        },
        "disk": {
            "path": "/",
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "usage_percent": disk.percent,
        },
        "uptime_seconds": uptime_seconds,
    }
