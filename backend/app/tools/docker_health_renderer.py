def render_docker_health_summary(result: dict) -> str:
    if not result.get("available", True):
        return "DOCKER HEALTH — VERIFIED\n\nDocker CLI: unavailable"

    healthy = result.get("healthy", [])
    unhealthy = result.get("unhealthy", [])
    unspecified = result.get("running_unspecified", [])
    stopped = result.get("stopped", [])

    lines = [
        "DOCKER HEALTH — VERIFIED",
        "",
        f"Explicitly unhealthy running containers: {len(unhealthy)}",
        f"Explicitly healthy running containers: {len(healthy)}",
        f"Running without explicit health status: {len(unspecified)}",
        f"Stopped/exited containers: {len(stopped)}",
        "",
    ]

    if unhealthy:
        lines.append("Explicitly unhealthy:")
        for item in unhealthy:
            lines.append(f"- {item.get('name')} | {item.get('status')}")
    else:
        lines.append(
            "No running container explicitly reports Docker health status 'unhealthy'."
        )

    if unspecified:
        lines.extend(["", "Running with no explicit Docker health status:"])
        for item in unspecified:
            lines.append(f"- {item.get('name')} | {item.get('status')}")

    if stopped:
        lines.extend(
            ["", "Stopped/exited (not classified as Docker-health unhealthy):"]
        )
        for item in stopped:
            lines.append(f"- {item.get('name')} | {item.get('status')}")

    return "\n".join(lines)
