from datetime import datetime, timezone


def evaluate_alerts(sample: dict) -> list[dict]:
    alerts: list[dict] = []

    def add(
        alert_id: str,
        severity: str,
        title: str,
        message: str,
        value=None,
        threshold=None,
    ) -> None:
        alerts.append(
            {
                "id": alert_id,
                "severity": severity,
                "title": title,
                "message": message,
                "value": value,
                "threshold": threshold,
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(),
            }
        )

    cpu = sample.get("cpu_percent", 0)
    memory = sample.get("memory_percent", 0)
    disk = sample.get("disk_percent", 0)

    services_reachable = sample.get(
        "services_reachable",
        0,
    )
    services_total = sample.get(
        "services_total",
        0,
    )

    docker_running = sample.get(
        "docker_running",
        0,
    )
    docker_total = sample.get(
        "docker_total",
        0,
    )

    latency = sample.get(
        "service_latency_ms",
        0,
    )

    if cpu >= 90:
        add(
            "cpu-critical",
            "critical",
            "High CPU Usage",
            f"CPU usage reached {cpu}%.",
            cpu,
            90,
        )
    elif cpu >= 75:
        add(
            "cpu-elevated",
            "warning",
            "Elevated CPU Usage",
            f"CPU usage reached {cpu}%.",
            cpu,
            75,
        )

    if memory >= 90:
        add(
            "memory-critical",
            "critical",
            "High Memory Usage",
            f"Memory usage reached {memory}%.",
            memory,
            90,
        )
    elif memory >= 80:
        add(
            "memory-elevated",
            "warning",
            "Elevated Memory Usage",
            f"Memory usage reached {memory}%.",
            memory,
            80,
        )

    if disk >= 95:
        add(
            "disk-critical",
            "critical",
            "Disk Space Critical",
            f"Disk usage reached {disk}%.",
            disk,
            95,
        )
    elif disk >= 85:
        add(
            "disk-elevated",
            "warning",
            "Disk Space Elevated",
            f"Disk usage reached {disk}%.",
            disk,
            85,
        )

    if (
        services_total > 0
        and services_reachable < services_total
    ):
        add(
            "service-failure",
            "critical",
            "Service Failure",
            (
                f"{services_reachable}/"
                f"{services_total} services reachable."
            ),
            services_reachable,
            services_total,
        )

    if latency >= 1000:
        add(
            "service-latency-critical",
            "critical",
            "Service Latency Critical",
            f"Average service latency is {latency} ms.",
            latency,
            1000,
        )
    elif latency >= 500:
        add(
            "service-latency-elevated",
            "warning",
            "Service Latency Elevated",
            f"Average service latency is {latency} ms.",
            latency,
            500,
        )

    return alerts
