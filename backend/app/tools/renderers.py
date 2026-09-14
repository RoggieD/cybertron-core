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

    if tool_id == "docker.inspect":
        return render_docker_inspect(result)

    if tool_id == "system.processes":
        return render_process_inventory(result)

    if tool_id == "network.interfaces":
        return render_network_interfaces(result)

    if tool_id == "network.listeners":
        return render_network_listeners(result)

    if tool_id == "network.port_owner":
        return render_port_owner(result)

    if tool_id == "network.reachability":
        return render_reachability(result)

    if tool_id == "service.status":
        return render_service_status(result)

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

    listener_requests = {
        "show listening ports",
        "show listening ports.",
        "show open ports",
        "show open ports.",
        "show network listeners",
        "show network listeners.",
        "what services are listening",
        "what services are listening.",
    }

    if tool_id == "network.listeners":
        return normalized in listener_requests

    if tool_id == "network.port_owner":
        return True

    if tool_id == "docker.inspect":
        return True

    if tool_id == "network.reachability":
        return True

    if tool_id == "service.status":
        return True

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


def render_network_listeners(result: dict) -> str:
    listeners = result.get("listeners", [])

    lines = [
        "NETWORK LISTENERS — VERIFIED",
        "",
        f"Listening sockets: {len(listeners)}",
        "",
        "Address | Port | PID | Process",
    ]

    for listener in listeners:
        lines.append(
            f"{listener.get('address', 'unknown')} | "
            f"{listener.get('port', 'unknown')} | "
            f"{listener.get('pid') or '-'} | "
            f"{listener.get('process') or 'unknown'}"
        )

    return "\n".join(lines)


def render_port_owner(result: dict) -> str:
    port = result.get("port")
    matches = result.get("matches", [])

    lines = [
        f"PORT {port} — VERIFIED",
        "",
        f"Listening: {'yes' if result.get('listening') else 'no'}",
        f"Bindings found: {result.get('count', len(matches))}",
    ]

    if not matches:
        return "\n".join(lines)

    lines.extend(
        [
            "",
            "Bindings:",
        ]
    )

    for match in matches:
        address = match.get("address", "unknown")
        pid = match.get("pid")
        process = match.get("process")

        display_address = (
            f"[{address}]"
            if ":" in str(address)
            else str(address)
        )

        lines.append(
            f"- {display_address}:{port} | "
            f"PID: {pid if pid is not None else 'unresolved'} | "
            f"Process: {process or 'unresolved'}"
        )

    unresolved = any(
        match.get("pid") is None
        or not match.get("process")
        for match in matches
    )

    if unresolved:
        lines.extend(
            [
                "",
                "Note:",
                (
                    "The listener is confirmed, but one or more owning "
                    "processes could not be resolved with the current "
                    "unprivileged inspection level."
                ),
            ]
        )

    return "\n".join(lines)


def render_docker_inspect(result: dict) -> str:
    requested = result.get("container") or "unknown"

    if not result.get("available", True):
        return (
            "DOCKER CONTAINER — VERIFIED\n\n"
            f"Container: {requested}\n"
            "Docker CLI: unavailable"
        )

    if not result.get("found"):
        error = result.get("error")

        lines = [
            "DOCKER CONTAINER — VERIFIED",
            "",
            f"Container: {requested}",
            "Found: no",
        ]

        if error:
            lines.extend(
                [
                    "",
                    "Details:",
                    error,
                ]
            )

        return "\n".join(lines)

    name = result.get("name") or requested
    image = result.get("image") or "unknown"
    status = result.get("status") or "unknown"
    health = result.get("health") or "not configured"
    restart_count = result.get("restart_count")

    lines = [
        "DOCKER CONTAINER — VERIFIED",
        "",
        f"Name: {name}",
        f"Image: {image}",
        f"Status: {status}",
        f"Health: {health}",
        f"Restart count: {restart_count if restart_count is not None else 'unknown'}",
    ]

    networks = result.get("networks") or []

    lines.extend(
        [
            "",
            "Networks:",
        ]
    )

    if networks:
        for network in networks:
            lines.append(f"- {network}")
    else:
        lines.append("- none reported")

    ports = result.get("ports") or {}

    lines.extend(
        [
            "",
            "Ports:",
        ]
    )

    if not ports:
        lines.append("- none published")
    else:
        for container_port, bindings in sorted(ports.items()):
            if not bindings:
                lines.append(
                    f"- {container_port} -> internal only / no host binding"
                )
                continue

            for binding in bindings:
                host_ip = binding.get("HostIp") or "0.0.0.0"
                host_port = binding.get("HostPort") or "unknown"

                display_ip = (
                    f"[{host_ip}]"
                    if ":" in str(host_ip)
                    else str(host_ip)
                )

                lines.append(
                    f"- {container_port} -> {display_ip}:{host_port}"
                )

    return "\n".join(lines)


def render_reachability(result: dict) -> str:
    check_type = result.get("type") or "unknown"
    target = result.get("target") or "unknown"
    reachable = bool(result.get("reachable"))
    latency = result.get("latency_ms")

    service_name = result.get("service_name")

    lines = [
        "SERVICE REACHABILITY — VERIFIED",
        "",
    ]

    if service_name:
        lines.append(f"Service: {service_name}")

    lines.extend(
        [
            f"Target: {target}",
            f"Reachable: {'yes' if reachable else 'no'}",
            f"Protocol: {check_type.upper()}",
        ]
    )

    if check_type == "http":
        status_code = result.get("status_code")
        reason = result.get("reason")
        final_url = result.get("final_url")

        if status_code is not None:
            status_text = str(status_code)

            if reason:
                status_text += f" {reason}"

            lines.append(
                f"HTTP status: {status_text}"
            )

        if final_url and final_url != target:
            lines.append(
                f"Final URL: {final_url}"
            )

    elif check_type == "tcp":
        host = result.get("host")
        port = result.get("port")

        if host:
            lines.append(f"Host: {host}")

        if port is not None:
            lines.append(f"Port: {port}")

    if latency is not None:
        lines.append(
            f"Latency: {latency} ms"
        )

    error = result.get("error")

    if error:
        lines.extend(
            [
                "",
                "Error:",
                str(error),
            ]
        )

    return "\n".join(lines)


def render_service_status(result: dict) -> str:
    total = result.get("total", 0)
    reachable = result.get("reachable", 0)
    unreachable = result.get("unreachable", 0)
    services = result.get("services") or []

    lines = [
        "SERVICE HEALTH SUMMARY — VERIFIED",
        "",
        f"Services checked: {total}",
        f"Reachable: {reachable}",
        f"Unreachable: {unreachable}",
        "",
        "Services:",
    ]

    for service in services:
        status = "UP" if service.get("reachable") else "DOWN"
        name = service.get("name") or "unknown"
        scope = service.get("scope") or "unknown"
        code = service.get("status_code")
        latency = service.get("latency_ms")

        detail = [
            f"- {status}",
            name,
            f"[{scope}]",
        ]

        if code is not None:
            detail.append(f"HTTP {code}")

        if latency is not None:
            detail.append(f"{latency} ms")

        lines.append(" | ".join(detail))

        error = service.get("error")

        if error:
            lines.append(f"  Error: {error}")

    return "\n".join(lines)
