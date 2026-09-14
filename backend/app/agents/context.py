import json


def format_tool_context(
    tool_id: str | None,
    result: dict | None,
) -> str:
    if not tool_id or result is None:
        return ""

    if tool_id == "system.snapshot":
        cpu = result.get("cpu", {})
        memory = result.get("memory", {})
        disk = result.get("disk", {})

        return f"""
VERIFIED TOOL DATA
Source: system.snapshot
Hostname: {result.get("hostname")}
CPU usage: {cpu.get("usage_percent")}%
Logical CPU cores: {cpu.get("logical_cores")}
Physical CPU cores: {cpu.get("physical_cores")}
Load average 1m: {cpu.get("load_average", {}).get("1m")}
Load average 5m: {cpu.get("load_average", {}).get("5m")}
Load average 15m: {cpu.get("load_average", {}).get("15m")}
Memory usage: {memory.get("usage_percent")}%
Disk usage: {disk.get("usage_percent")}%
Uptime seconds: {result.get("uptime_seconds")}

Rules:
- Treat these values as verified facts.
- Do not substitute estimated or invented values.
- Answer the user's actual question first.
""".strip()

    if tool_id == "docker.inventory":
        containers = result.get("containers", [])
        expected_count = result.get("count", len(containers))

        lines = [
            "VERIFIED TOOL DATA",
            "Source: docker.inventory",
            f"Docker available: {result.get('available')}",
            f"VERIFIED CONTAINER COUNT: {expected_count}",
            "",
            "VERIFIED CONTAINERS:",
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
                "Rules:",
                f"- The verified total is exactly {expected_count} containers.",
                "- Never report a different total.",
                "- Do not silently omit containers and call the subset the total.",
                "- If summarizing only running containers, explicitly label it as a subset.",
                "- When the user asks to inspect Docker without narrowing the request, report all containers.",
                "- Distinguish running, healthy, unhealthy, and exited states exactly from the supplied status.",
                "- Do not invent project names, health states, ports, or relationships.",
            ]
        )

        return "\n".join(lines)

    if tool_id == "memory.search":
        count = int(result.get("count", 0) or 0)
        scope = result.get("scope", "unknown")
        allowed = bool(result.get("allowed", False))
        memories = result.get("memories") or []

        lines = [
            "VERIFIED TOOL DATA",
            "Source: memory.search",
            f"Search allowed: {allowed}",
            f"Search scope: {scope}",
            f"Matches returned by this specific search: {count}",
            "",
            "Interpretation rules:",
            (
                "- This result describes only this explicit memory.search "
                "invocation and its query/scope."
            ),
            (
                "- A zero match count means this specific search found no "
                "additional matching records."
            ),
            (
                "- Never infer from a zero result that persistent memory is "
                "empty or that separately injected verified memory context "
                "does not exist."
            ),
            (
                "- If VERIFIED PERSISTENT MEMORY — CONTEXT RETRIEVAL appears "
                "elsewhere in the system prompt, preserve those records as "
                "valid context even when this tool result is zero."
            ),
        ]

        if memories:
            lines.extend(["", "MATCHING RECORDS:"])
            for index, memory in enumerate(memories, start=1):
                lines.append(
                    f"{index}. [{memory.get('kind', 'unknown')}] "
                    f"{memory.get('content', '')} "
                    f"(scope: {memory.get('scope', 'unknown')}; "
                    f"source: {memory.get('source') or 'unknown'})"
                )

        return "\n".join(lines)

    return (
        "VERIFIED TOOL DATA\n"
        f"Source: {tool_id}\n"
        f"{json.dumps(result, indent=2, default=str)}\n\n"
        "Treat this data as authoritative. Do not alter verified facts."
    )
