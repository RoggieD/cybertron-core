import os
import platform
import subprocess
import time

import psutil


def _empty_gpu_snapshot() -> dict:
    return {
        "available": False,
        "name": None,
        "usage_percent": None,
        "memory_used_mb": None,
        "memory_total_mb": None,
        "memory_usage_percent": None,
        "temperature_c": None,
        "power_draw_watts": None,
        "power_limit_watts": None,
        "power_usage_percent": None,
    }


def _gpu_snapshot() -> dict:
    """Read NVIDIA GPU telemetry without making it a hard dependency.

    C.O.R.E. runs on systems that may not have NVIDIA hardware, so failures are
    reported as unavailable telemetry rather than failing the system snapshot.
    """
    command = [
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
        "--format=csv,noheader,nounits",
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return _empty_gpu_snapshot()

    line = next(
        (item.strip() for item in result.stdout.splitlines() if item.strip()),
        "",
    )
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 7:
        return _empty_gpu_snapshot()

    try:
        name = parts[0]
        usage_percent = float(parts[1])
        memory_used_mb = float(parts[2])
        memory_total_mb = float(parts[3])
        temperature_c = float(parts[4])
        power_draw_watts = float(parts[5])
        power_limit_watts = float(parts[6])
        memory_usage_percent = (
            (memory_used_mb / memory_total_mb) * 100.0
            if memory_total_mb > 0
            else 0.0
        )
        power_usage_percent = (
            (power_draw_watts / power_limit_watts) * 100.0
            if power_limit_watts > 0
            else 0.0
        )
    except ValueError:
        return _empty_gpu_snapshot()

    return {
        "available": True,
        "name": name,
        "usage_percent": round(usage_percent, 1),
        "memory_used_mb": round(memory_used_mb, 1),
        "memory_total_mb": round(memory_total_mb, 1),
        "memory_usage_percent": round(memory_usage_percent, 1),
        "temperature_c": round(temperature_c, 1),
        "power_draw_watts": round(power_draw_watts, 1),
        "power_limit_watts": round(power_limit_watts, 1),
        "power_usage_percent": round(power_usage_percent, 1),
    }


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
        "gpu": _gpu_snapshot(),
        "uptime_seconds": uptime_seconds,
    }
