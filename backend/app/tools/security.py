import asyncio
from datetime import datetime, timezone

from backend.app.tools.listeners import listener_inventory
from backend.app.tools.processes import process_inventory
from backend.app.tools.system import system_snapshot


PUBLIC_BIND_ADDRESSES = {
    "0.0.0.0",
    "::",
    "::0",
}


def _severity_rank(value: str) -> int:
    return {
        "info": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
    }.get(value, 0)


async def security_snapshot() -> dict:
    """Build a deterministic, read-only defensive posture snapshot.

    This intentionally performs local observation only. It does not probe
    external systems, exploit services, alter firewall state, or make claims
    about compromise. Findings are evidence-backed observations that can be
    used by the Security Agent and provenance graph.
    """

    system, listeners, processes = await asyncio.gather(
        system_snapshot(),
        listener_inventory(),
        process_inventory(),
    )

    findings: list[dict] = []

    public_listeners = [
        listener
        for listener in listeners.get("listeners", [])
        if listener.get("address") in PUBLIC_BIND_ADDRESSES
    ]

    unknown_owner_listeners = [
        listener
        for listener in listeners.get("listeners", [])
        if not listener.get("process")
    ]

    if public_listeners:
        findings.append(
            {
                "id": "public-listeners",
                "severity": "medium",
                "category": "attack-surface",
                "title": "Services listening on all interfaces",
                "evidence_count": len(public_listeners),
                "evidence": public_listeners[:20],
                "interpretation": (
                    "These listeners are reachable on every configured local "
                    "interface unless constrained by host or upstream firewall policy."
                ),
            }
        )

    if unknown_owner_listeners:
        findings.append(
            {
                "id": "unknown-listener-owner",
                "severity": "low",
                "category": "visibility",
                "title": "Listener ownership could not be resolved",
                "evidence_count": len(unknown_owner_listeners),
                "evidence": unknown_owner_listeners[:20],
                "interpretation": (
                    "C.O.R.E. could see the listening socket but could not "
                    "attribute it to a process with current permissions."
                ),
            }
        )

    memory_percent = float(system.get("memory", {}).get("usage_percent") or 0.0)
    disk_percent = float(system.get("disk", {}).get("usage_percent") or 0.0)
    cpu_percent = float(system.get("cpu", {}).get("usage_percent") or 0.0)

    pressure = []
    if cpu_percent >= 90:
        pressure.append({"resource": "cpu", "usage_percent": cpu_percent})
    if memory_percent >= 90:
        pressure.append({"resource": "memory", "usage_percent": memory_percent})
    if disk_percent >= 90:
        pressure.append({"resource": "disk", "usage_percent": disk_percent})

    if pressure:
        findings.append(
            {
                "id": "resource-pressure",
                "severity": "medium",
                "category": "resilience",
                "title": "High local resource pressure",
                "evidence_count": len(pressure),
                "evidence": pressure,
                "interpretation": (
                    "Sustained resource pressure can reduce visibility, "
                    "availability, and defensive response capacity."
                ),
            }
        )

    hot_processes = [
        process
        for process in processes.get("processes", [])
        if float(process.get("cpu_percent") or 0.0) >= 70.0
        or float(process.get("memory_percent") or 0.0) >= 25.0
    ]

    if hot_processes:
        findings.append(
            {
                "id": "high-resource-processes",
                "severity": "low",
                "category": "behavior",
                "title": "High-resource processes observed",
                "evidence_count": len(hot_processes),
                "evidence": hot_processes[:10],
                "interpretation": (
                    "This is an operational observation, not an indicator of compromise. "
                    "It can be correlated with incidents or later baselines."
                ),
            }
        )

    findings.sort(
        key=lambda item: _severity_rank(item["severity"]),
        reverse=True,
    )

    severity_counts = {
        severity: sum(1 for item in findings if item["severity"] == severity)
        for severity in ("high", "medium", "low", "info")
    }

    score = min(
        100,
        severity_counts["high"] * 35
        + severity_counts["medium"] * 18
        + severity_counts["low"] * 7,
    )

    if score >= 60:
        posture = "high-attention"
    elif score >= 30:
        posture = "elevated"
    elif score > 0:
        posture = "observed"
    else:
        posture = "baseline"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local-read-only",
        "posture": posture,
        "attention_score": score,
        "finding_count": len(findings),
        "severity_counts": severity_counts,
        "findings": findings,
        "evidence": {
            "hostname": system.get("hostname"),
            "listener_count": listeners.get("count", 0),
            "public_listener_count": len(public_listeners),
            "unknown_owner_listener_count": len(unknown_owner_listeners),
            "process_count": processes.get("count", 0),
            "returned_process_count": processes.get("returned", 0),
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory_percent,
            "disk_usage_percent": disk_percent,
        },
        "limitations": [
            "Local host observation only.",
            "No external network scanning was performed.",
            "No vulnerability database lookup was performed.",
            "Findings are observations and do not prove compromise.",
        ],
    }
