def render_docker_inventory(result: dict) -> str:
    containers = result.get("containers", [])

    running = []
    exited = []
    healthy = []
    running_unspecified = []

    for container in containers:
        status = str(container.get("Status", ""))
        status_lower = status.lower()

        if status_lower.startswith("up"):
            running.append(container)

            if "(healthy)" in status_lower:
                healthy.append(container)
            else:
                running_unspecified.append(container)
        else:
            exited.append(container)

    lines = [
        "DOCKER INVENTORY — VERIFIED",
        "",
        f"Total containers: {len(containers)}",
        f"Running containers: {len(running)}",
        f"Healthy containers: {len(healthy)}",
        f"Running without explicit health status: {len(running_unspecified)}",
        f"Stopped/exited containers: {len(exited)}",
        "",
        "Containers:",
    ]

    for index, container in enumerate(containers, start=1):
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
            f"- {len(running)} of {len(containers)} containers are running.",
            f"- {len(healthy)} running containers explicitly report healthy status.",
            f"- {len(running_unspecified)} running containers have no explicit Docker health status.",
            f"- {len(exited)} containers are stopped/exited.",
        ]
    )

    if exited:
        lines.append("")
        lines.append("Stopped/exited containers:")

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

    if tool_id == "docker.inventory":
        return render_docker_inventory(result)

    return None


def should_return_verified_only(
    message: str,
    tool_id: str | None,
) -> bool:
    if tool_id != "docker.inventory":
        return False

    normalized = " ".join(
        message.lower().strip().split()
    )

    direct_inventory_requests = {
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

    return normalized in direct_inventory_requests
