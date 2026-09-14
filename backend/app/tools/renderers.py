def bytes_to_gib(value: int | None) -> float:
    if not value:
        return 0.0

    return value / (1024 ** 3)


def render_system_snapshot(result: dict) -> str:
    cpu = result.get("cpu", {})
    memory = result.get("memory", {})
    disk = result.get("disk", {})
    load = cpu.get("load_average", {})

    uptime_seconds = int(
        result.get("uptime_seconds", 0)
    )

    days, remainder = divmod(
        uptime_seconds,
        86400,
    )

    hours, remainder = divmod(
        remainder,
        3600,
    )

    minutes, _ = divmod(
        remainder,
        60,
    )

    lines = [
        "SYSTEM STATUS — VERIFIED",
        "",
        f"Hostname: {result.get('hostname', 'unknown')}",
        f"Platform: {result.get('platform', 'unknown')}",
        "",
        f"CPU usage: {cpu.get('usage_percent')}%",
        f"Physical cores: {cpu.get('physical_cores')}",
        f"Logical cores: {cpu.get('logical_cores')}",
        (
            "Load average: "
            f"{load.get('1m')} / "
            f"{load.get('5m')} / "
            f"{load.get('15m')}"
        ),
        "",
        (
            "Memory usage: "
            f"{memory.get('usage_percent')}%"
        ),
        (
            "Memory used: "
            f"{bytes_to_gib(memory.get('used_bytes')):.1f} GiB"
        ),
        (
            "Memory available: "
            f"{bytes_to_gib(memory.get('available_bytes')):.1f} GiB"
        ),
        (
            "Memory total: "
            f"{bytes_to_gib(memory.get('total_bytes')):.1f} GiB"
        ),
        "",
        (
            "Disk usage: "
            f"{disk.get('usage_percent')}%"
        ),
        (
            "Disk used: "
            f"{bytes_to_gib(disk.get('used_bytes')):.1f} GiB"
        ),
        (
            "Disk free: "
            f"{bytes_to_gib(disk.get('free_bytes')):.1f} GiB"
        ),
        (
            "Disk total: "
            f"{bytes_to_gib(disk.get('total_bytes')):.1f} GiB"
        ),
        "",
        (
            "Uptime: "
            f"{days}d {hours}h {minutes}m"
        ),
    ]

    return "\n".join(lines)


def render_docker_inventory(result: dict) -> str:
    containers = result.get("containers", [])

    running = []
    exited = []
    healthy = []
    running_unspecified = []

    for container in containers:
        status = str(
            container.get("Status", "")
        )
        status_lower = status.lower()

        if status_lower.startswith("up"):
            running.append(container)

            if "(healthy)" in status_lower:
                healthy.append(container)
            else:
                running_unspecified.append(
                    container
                )
        else:
            exited.append(container)

    lines = [
        "DOCKER INVENTORY — VERIFIED",
        "",
        f"Total containers: {len(containers)}",
        f"Running containers: {len(running)}",
        f"Healthy containers: {len(healthy)}",
        (
            "Running without explicit health status: "
            f"{len(running_unspecified)}"
        ),
        (
            "Stopped/exited containers: "
            f"{len(exited)}"
        ),
        "",
        "Containers:",
    ]

    for index, container in enumerate(
        containers,
        start=1,
    ):
        lines.append(
            f"{index}. "
            f"{container.get('Names', 'unknown')} | "
            f"{container.get('Status', 'unknown')} | "
            f"{container.get('Image', 'unknown')}"
        )

    lines.extend(
        [
            "",
            "VERIFIED OBSERVATIONS",
            (
                f"{len(running)} of {len(containers)} "
                "containers are running."
            ),
            (
                f"{len(healthy)} running containers "
                "explicitly report healthy status."
            ),
            (
                f"{len(running_unspecified)} running "
                "containers have no explicit Docker "
                "health status."
            ),
            (
                f"{len(exited)} containers are "
                "stopped/exited."
            ),
        ]
    )

    if exited:
        lines.append("")
        lines.append(
            "Stopped/exited containers:"
        )

        for container in exited:
            lines.append(
                f"- {container.get('Names', 'unknown')} | "
                f"{container.get('Status', 'unknown')}"
            )

    return "\n".join(lines)


def render_verified_tool_result(
    tool_id: str | None,
    result: dict | None,
) -> str | None:
    if not tool_id or result is None:
        return None

    if tool_id == "system.snapshot":
        return render_system_snapshot(result)

    if tool_id == "docker.inventory":
        return render_docker_inventory(result)

    if tool_id == "system.processes":
        return render_process_inventory(result)

    if tool_id == "network.interfaces":
        return render_network_interfaces(result)

    return None


def should_return_verified_only(
    message: str,
    tool_id: str | None,
) -> bool:
    normalized = " ".join(
        message.lower().strip().split()
    )

    docker_requests = {
        "inspect docker",
        "inspect docker.",
        "show docker",
        "show docker.",
        "show docker status",
        "show docker status.",
        "list docker containers",
        "list docker containers.",
        "show containers",
        "show containers.",
    }

    system_requests = {
        "show cpu usage",
        "show cpu usage.",
        "show system status",
        "show system status.",
        "show system stats",
        "show system stats.",
        "system status",
        "system status.",
        "show memory usage",
        "show memory usage.",
        "show disk usage",
        "show disk usage.",
        "show uptime",
        "show uptime.",
    }

    if tool_id == "docker.inventory":
        return normalized in docker_requests

    if tool_id == "system.snapshot":
        return normalized in system_requests

    process_requests = {
        "show running processes",
        "show running processes.",
        "show processes",
        "show processes.",
        "list processes",
        "list processes.",
        "show top processes",
        "show top processes.",
    }

    network_requests = {
        "show network interfaces",
        "show network interfaces.",
        "show interfaces",
        "show interfaces.",
        "show ip addresses",
        "show ip addresses.",
        "show network",
        "show network.",
    }

    if tool_id == "system.processes":
        return normalized in process_requests

    if tool_id == "network.interfaces":
        return normalized in network_requests

    return False


def render_process_inventory(result: dict) -> str:
    processes = result.get("processes", [])

    lines = [
        "PROCESS INVENTORY — VERIFIED",
        "",
        f"Total processes observed: {result.get('count', 0)}",
        f"Processes returned: {result.get('returned', len(processes))}",
        "",
        "Top returned processes:",
    ]

    for index, process in enumerate(processes, start=1):
        lines.append(
            f"{index}. "
            f"PID {process.get('pid')} | "
            f"{process.get('name', 'unknown')} | "
            f"CPU {process.get('cpu_percent', 0)}% | "
            f"MEM {process.get('memory_percent', 0)}% | "
            f"STATUS {process.get('status', 'unknown')}"
        )

    return "\n".join(lines)


def render_network_interfaces(result: dict) -> str:
    interfaces = result.get("interfaces", [])

    lines = [
        "NETWORK INTERFACES — VERIFIED",
        "",
        f"Interface count: {result.get('count', len(interfaces))}",
        "",
    ]

    for interface in interfaces:
        lines.append(
            f"{interface.get('name', 'unknown')} | "
            f"UP: {interface.get('up')} | "
            f"SPEED: {interface.get('speed_mbps')} Mbps | "
            f"MTU: {interface.get('mtu')}"
        )

        for address in interface.get("addresses", []):
            lines.append(
                f"  - {address.get('family')} | "
                f"{address.get('address')} | "
                f"netmask {address.get('netmask')}"
            )

    return "\n".join(lines)
