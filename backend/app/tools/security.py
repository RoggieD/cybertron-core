import asyncio
from datetime import datetime, timezone

from backend.app.security_baseline import security_baseline_store
from backend.app.security_policy import security_policy_store
from backend.app.tools.listeners import listener_inventory
from backend.app.tools.processes import process_inventory
from backend.app.tools.system import system_snapshot


PUBLIC_BIND_ADDRESSES = {
    "0.0.0.0",
    "::",
    "::0",
}

LOOPBACK_ADDRESSES = {
    "127.0.0.1",
    "::1",
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


def _endpoint_address(endpoint: str) -> str:
    """Return the address portion of an address:port endpoint string."""
    if endpoint.startswith("[") and "]:" in endpoint:
        return endpoint[1:].rsplit("]:", 1)[0]
    if endpoint.count(":") == 1:
        return endpoint.split(":", 1)[0]
    return endpoint.rsplit(":", 1)[0]


def _is_loopback_endpoint(endpoint: str) -> bool:
    return _endpoint_address(endpoint) in LOOPBACK_ADDRESSES


async def security_snapshot() -> dict:
    """Build a deterministic, local defensive posture snapshot.

    Observation is read-only with respect to the host. C.O.R.E. records the
    snapshot as defensive telemetry, maintains a learned public-listener
    baseline, and enforces administrator-approved public-listener policy when
    one has been explicitly created.
    """

    system, listeners, processes = await asyncio.gather(
        system_snapshot(),
        listener_inventory(),
        process_inventory(),
    )

    findings: list[dict] = []
    all_listeners = listeners.get("listeners", [])

    public_listeners = [
        listener
        for listener in all_listeners
        if listener.get("address") in PUBLIC_BIND_ADDRESSES
    ]

    unknown_owner_listeners = [
        listener
        for listener in all_listeners
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
                    "These sockets are bound to every configured local interface. "
                    "Remote reachability still depends on host and upstream firewall "
                    "policy; an all-interface bind alone does not prove Internet exposure."
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

    _, base_score, base_posture = _score_findings(findings)

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
            "listeners": all_listeners,
            "processes": processes.get("processes", []),
        },
    }

    baseline_comparison, expected_listener_policy, approved_listener_policy = await asyncio.gather(
        security_baseline_store.compare_and_record(telemetry_record),
        security_baseline_store.compare_expected_public_listeners(
            evidence.get("hostname"),
            generated_at,
            all_listeners,
        ),
        security_policy_store.evaluate(
            evidence.get("hostname"),
            all_listeners,
        ),
    )

    if approved_listener_policy.get("approved_configured"):
        policy_mode = "administrator-approved"
        unexpected_public = approved_listener_policy.get(
            "unexpected_public_listener_endpoints", []
        )
        missing_expected_public = approved_listener_policy.get(
            "missing_approved_public_listener_endpoints", []
        )
    else:
        policy_mode = "learned-baseline"
        unexpected_public = expected_listener_policy.get(
            "unexpected_public_listener_endpoints", []
        )
        missing_expected_public = expected_listener_policy.get(
            "missing_expected_public_listener_endpoints", []
        )

    if unexpected_public:
        findings.append(
            {
                "id": "unexpected-public-listener",
                "severity": "high",
                "category": "approved-policy-drift"
                if policy_mode == "administrator-approved"
                else "expected-state-drift",
                "title": "Unapproved all-interface listener detected"
                if policy_mode == "administrator-approved"
                else "Unexpected all-interface listener detected",
                "evidence_count": len(unexpected_public),
                "evidence": unexpected_public,
                "interpretation": (
                    "These all-interface listener endpoints are not present in the "
                    "administrator-approved listener policy. Treat them as unapproved "
                    "exposure until explicitly reviewed."
                    if policy_mode == "administrator-approved"
                    else
                    "These all-interface listener endpoints are not present in the "
                    "host's learned expected-listener baseline. Validate the service "
                    "and exposure before treating it as approved."
                ),
            }
        )

    if missing_expected_public:
        findings.append(
            {
                "id": "approved-public-listener-missing"
                if policy_mode == "administrator-approved"
                else "expected-public-listener-missing",
                "severity": "low",
                "category": "approved-policy-drift"
                if policy_mode == "administrator-approved"
                else "expected-state-drift",
                "title": "Approved public listener is no longer present"
                if policy_mode == "administrator-approved"
                else "Expected public listener is no longer present",
                "evidence_count": len(missing_expected_public),
                "evidence": missing_expected_public,
                "interpretation": (
                    "An administrator-approved listener is absent. Correlate the change "
                    "with service health and maintenance activity."
                    if policy_mode == "administrator-approved"
                    else
                    "One or more previously expected all-interface listeners are absent. "
                    "This may be normal maintenance or a stopped service and should be "
                    "correlated with service health."
                ),
            }
        )

    loopback_new: list[str] = []
    reviewable_new: list[str] = []

    if baseline_comparison.get("has_previous_baseline"):
        new_endpoints = baseline_comparison.get("new_listener_endpoints", [])
        removed_endpoints = baseline_comparison.get("removed_listener_endpoints", [])
        new_public = set(
            baseline_comparison.get("new_public_listener_endpoints", [])
        )

        non_public_new = [
            endpoint for endpoint in new_endpoints if endpoint not in new_public
        ]
        loopback_new = [
            endpoint for endpoint in non_public_new if _is_loopback_endpoint(endpoint)
        ]
        reviewable_new = [
            endpoint for endpoint in non_public_new if endpoint not in loopback_new
        ]

        if reviewable_new:
            findings.append(
                {
                    "id": "security-relevant-change",
                    "severity": "medium",
                    "category": "change-detection",
                    "title": "New non-loopback listening endpoint detected",
                    "evidence_count": len(reviewable_new),
                    "evidence": {
                        "new_non_loopback_listener_endpoints": reviewable_new,
                    },
                    "interpretation": (
                        "C.O.R.E. detected a newly listening endpoint that is not "
                        "limited to loopback and is not an all-interface listener already "
                        "handled by listener policy. Validate that the exposure is expected."
                    ),
                }
            )
        elif removed_endpoints and not missing_expected_public:
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
        "listener_policy_mode": policy_mode,
        "approved_listener_policy": approved_listener_policy,
        "expected_listener_policy": expected_listener_policy,
        "baseline_comparison": baseline_comparison,
        "baseline_context": {
            "process_churn_is_context_only": True,
            "new_process_names": baseline_comparison.get("new_process_names", []),
            "removed_process_names": baseline_comparison.get("removed_process_names", []),
            "listener_owner_changes": baseline_comparison.get("listener_owner_changes", []),
            "new_loopback_listener_endpoints": loopback_new,
            "transient_score_and_posture_changes_are_context_only": True,
        },
        "limitations": [
            "Local host observation only.",
            "No external network scanning was performed.",
            "No vulnerability database lookup was performed.",
            (
                "Administrator-approved public-listener policy is authoritative for "
                "public exposure drift detection."
                if policy_mode == "administrator-approved"
                else
                "The expected listener baseline is learned from first observation and "
                "is not yet an administrator-approved allowlist."
            ),
            "Process churn, loopback listener churn, and transient load changes are retained as context and do not raise change findings by themselves.",
            "Unresolved listener ownership is a visibility limitation, not proof of suspicious activity.",
            "Changes from baseline are observations and do not prove compromise.",
            "Each security.snapshot call records defensive telemetry for later comparison.",
        ],
    }
