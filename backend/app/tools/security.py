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


def _score_findings(findings: list[dict]) -> tuple[dict, int, str]:
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

    return severity_counts, score, posture


async def security_snapshot() -> dict:
    """Build a deterministic, local defensive posture snapshot.

    Observation is read-only with respect to the host. C.O.R.E. records the
    snapshot as defensive telemetry so later assessments can detect meaningful
    exposure changes without treating ordinary process churn as an alert.
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
                "id": "listener-owner-visibility",
                "severity": "info",
                "category": "visibility",
                "title": "Listener ownership visibility is incomplete",
                "evidence_count": len(unknown_owner_listeners),
                "evidence": unknown_owner_listeners[:20],
                "interpretation": (
                    "C.O.R.E. can see these sockets but current permissions did not "
                    "resolve their owning processes. Treat this as a visibility "
                    "limitation, not suspicious activity by itself."
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
                    "This is operational context, not an indicator of compromise. "
                    "It becomes more useful when correlated with exposure changes."
                ),
            }
        )

    base_severity_counts, base_score, base_posture = _score_findings(findings)

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
        "posture": base_posture,
        "attention_score": base_score,
        "evidence": evidence,
        "raw_evidence": {
            "listeners": listeners.get("listeners", []),
            "processes": processes.get("processes", []),
        },
    }

    baseline_comparison = await security_baseline_store.compare_and_record(
        telemetry_record
    )

    if baseline_comparison.get("has_previous_baseline"):
        new_public = baseline_comparison.get("new_public_listener_endpoints", [])
        new_endpoints = baseline_comparison.get("new_listener_endpoints", [])
        removed_endpoints = baseline_comparison.get("removed_listener_endpoints", [])
        posture_changed = bool(baseline_comparison.get("posture_changed"))
        score_delta = int(baseline_comparison.get("attention_score_delta") or 0)

        if new_public:
            findings.append(
                {
                    "id": "new-public-exposure",
                    "severity": "high",
                    "category": "change-detection",
                    "title": "New externally bound listener detected",
                    "evidence_count": len(new_public),
                    "evidence": new_public,
                    "interpretation": (
                        "A listener now exists on an all-interface bind that was not "
                        "present in the immediately previous defensive snapshot. "
                        "Validate that the service and exposure are expected."
                    ),
                }
            )
        elif new_endpoints or posture_changed or score_delta > 0:
            findings.append(
                {
                    "id": "security-relevant-change",
                    "severity": "medium",
                    "category": "change-detection",
                    "title": "Security-relevant host state changed",
                    "evidence_count": len(new_endpoints),
                    "evidence": {
                        "new_listener_endpoints": new_endpoints,
                        "posture_changed": posture_changed,
                        "attention_score_delta": score_delta,
                    },
                    "interpretation": (
                        "C.O.R.E. detected an exposure or posture change worth review. "
                        "This is an observation and does not prove compromise."
                    ),
                }
            )
        elif removed_endpoints:
            findings.append(
                {
                    "id": "listener-reduction",
                    "severity": "low",
                    "category": "change-detection",
                    "title": "Listening endpoint removed since prior snapshot",
                    "evidence_count": len(removed_endpoints),
                    "evidence": removed_endpoints,
                    "interpretation": (
                        "A previously observed listening endpoint is no longer present. "
                        "This is generally lower priority unless an expected service disappeared."
                    ),
                }
            )

    findings.sort(
        key=lambda item: _severity_rank(item["severity"]),
        reverse=True,
    )
    severity_counts, score, posture = _score_findings(findings)

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
        "baseline_context": {
            "process_churn_is_context_only": True,
            "new_process_names": baseline_comparison.get("new_process_names", []),
            "removed_process_names": baseline_comparison.get("removed_process_names", []),
            "listener_owner_changes": baseline_comparison.get("listener_owner_changes", []),
        },
        "limitations": [
            "Local host observation only.",
            "No external network scanning was performed.",
            "No vulnerability database lookup was performed.",
            "Process churn alone is retained as context and does not raise a change finding.",
            "Unresolved listener ownership is a visibility limitation, not proof of suspicious activity.",
            "Changes from baseline are observations and do not prove compromise.",
            "Each security.snapshot call records defensive telemetry for later comparison.",
        ],
    }
