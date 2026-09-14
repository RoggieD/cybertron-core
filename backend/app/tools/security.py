import asyncio
from datetime import datetime, timezone

from backend.app.security_baseline import security_baseline_store
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
    """Build a deterministic, local defensive posture snapshot.

    Observation is read-only with respect to the host. C.O.R.E. records the
    snapshot as defensive telemetry so later assessments can detect changes in
    listeners, process names, attention score, and posture. It does not probe
    external systems, exploit services, or alter host configuration.
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

    generated_at = datetime.now(timezone.utc).isoformat()
    evidence = {
        "hostname": system.get("hostname"),
        "listener_count": listeners.get("count", 0),
        "public_listener_count": len(public_listeners),
        "unknown_owner_listener_count": len(unknown_owner_listeners),
        "process_count": processes.get("count", 0),
        "returned_process_count": processes.get("returned", 0),
        "cpu_usage_percent": cpu_percent,
        "memory_usage_percent": memory_percent,
        "disk_usage_percent": disk_percent,
    }

    telemetry_record = {
        "generated_at": generated_at,
        "posture": posture,
        "attention_score": score,
        "evidence": evidence,
        "raw_evidence": {
            "listeners": listeners.get("listeners", []),
            "processes": processes.get("processes", []),
        },
    }

    baseline_comparison = await security_baseline_store.compare_and_record(
        telemetry_record
    )

    if baseline_comparison.get("has_previous_baseline") and baseline_comparison.get("changed"):
        findings.insert(
            0,
            {
                "id": "baseline-change",
                "severity": "medium"
                if baseline_comparison.get("new_listeners")
                else "low",
                "category": "change-detection",
                "title": "Security-relevant host state changed since prior snapshot",
                "evidence_count": (
                    len(baseline_comparison.get("new_listeners", []))
                    + len(baseline_comparison.get("removed_listeners", []))
                    + len(baseline_comparison.get("new_process_names", []))
                    + len(baseline_comparison.get("removed_process_names", []))
                ),
                "evidence": baseline_comparison,
                "interpretation": (
                    "C.O.R.E. detected a difference from the immediately previous "
                    "defensive snapshot. Changes are observations and require context "
                    "before being treated as suspicious."
                ),
            },
        )

    return {
        "generated_at": generated_at,
        "mode": "local-read-only-observation",
        "posture": posture,
        "attention_score": score,
        "finding_count": len(findings),
        "severity_counts": severity_counts,
        "findings": findings,
        "evidence": evidence,
        "baseline_comparison": baseline_comparison,
        "limitations": [
            "Local host observation only.",
            "No external network scanning was performed.",
            "No vulnerability database lookup was performed.",
            "Changes from baseline are observations and do not prove compromise.",
            "Each security.snapshot call records defensive telemetry for later comparison.",
        ],
    }
