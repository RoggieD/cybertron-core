from backend.app.services.catalog import resolve_service
import re

from backend.app.agents.base import AgentDefinition
from backend.app.tools.registry import execute_tool
from backend.app.memory.episodic_retrieval import RECALL


def extract_port(message: str) -> int | None:
    match = re.search(
        r"\bport\s+(\d{1,5})\b",
        message.lower(),
    )

    if not match:
        return None

    port = int(match.group(1))

    if 1 <= port <= 65535:
        return port

    return None


def select_tool(
    agent: AgentDefinition,
    message: str,
) -> tuple[str | None, dict]:
    normalized = message.lower()

    memory_query = extract_memory_query(
        message
    )

    if memory_query is not None:
        return "memory.search", {
            "query": memory_query,
            "scope": "all",
        }

    # Historical recall is supplied by build_messages, not an implicit live
    # inspection. In particular, "what happened last time" must not fall into
    # the broad "what happened" incident-summary shortcut below.
    if RECALL.search(message):
        return None, {}

    if agent.id == "security":
        return "security.snapshot", {}

    if agent.id == "system":
        overview_phrases = (
            "system overview",
            "status report",
            "core status",
            "c.o.r.e. status",
            "cybertron doing",
            "how is cybertron",
        )

        if any(
            phrase in normalized
            for phrase in overview_phrases
        ):
            return "system.overview", {}

        process_terms = (
            "process",
            "processes",
            "running processes",
            "top processes",
        )

        if any(term in normalized for term in process_terms):
            return "system.processes", {}

        return "system.snapshot", {}

    if agent.id == "infrastructure":
        incident_clock = extract_incident_clock(
            message
        )

        incident_severity = (
            "critical"
            if "critical" in normalized
            else None
        )

        if incident_clock is not None:
            clock_hour, clock_minute = (
                incident_clock
            )

            return "incident.summary", {
                "mode": "since_clock",
                "hour": clock_hour,
                "minute": clock_minute,
                "severity": incident_severity,
            }

        if "yesterday" in normalized:
            return "incident.summary", {
                "mode": "yesterday",
                "severity": incident_severity,
            }

        incident_hours = extract_incident_hours(
            message
        )

        incident_severity = (
            "critical"
            if "critical" in normalized
            else None
        )

        if incident_hours is not None:
            return "incident.summary", {
                "mode": "time_window",
                "hours": incident_hours,
                "severity": incident_severity,
            }

        if "since midnight" in normalized:
            return "incident.summary", {
                "mode": "since_midnight",
                "severity": incident_severity,
            }

        if (
            "what failed today" in normalized
            or "incidents today" in normalized
            or "incident today" in normalized
        ):
            return "incident.summary", {
                "mode": "today",
                "severity": incident_severity,
            }

        if any(
            phrase in normalized
            for phrase in (
                "incident",
                "incidents",
                "what keeps failing",
                "failures",
                "overnight",
                "usually last",
                "last hour",
                "past hour",
                "last 24 hours",
                "since midnight",
                "today",
                "what happened",
                "what failed",
            )
        ):
            hours = extract_incident_hours(message)

            severity = (
                "critical"
                if "critical" in normalized
                else None
            )

            if hours is not None:
                return "incident.summary", {
                    "mode": "time_window",
                    "hours": hours,
                    "severity": severity,
                }

            if "since midnight" in normalized:
                return "incident.summary", {
                    "mode": "since_midnight",
                    "severity": severity,
                }

            if "today" in normalized:
                return "incident.summary", {
                    "mode": "today",
                    "severity": severity,
                }

            if (
                "critical" in normalized
                or "critical only" in normalized
            ):
                return "incident.summary", {
                    "mode": "critical",
                }

            if "overnight" in normalized:
                return "incident.summary", {
                    "mode": "overnight",
                }

            if (
                "what keeps failing" in normalized
                or "failures" in normalized
            ):
                return "incident.summary", {
                    "mode": "recurring",
                }

            if (
                "usually last" in normalized
                or "how long" in normalized
            ):
                return "incident.summary", {
                    "mode": "duration",
                }

            return "incident.summary", {
                "mode": "recent",
            }

        if any(
            phrase in normalized
            for phrase in (
                "service status",
                "services are up",
                "services up",
                "health summary",
                "service health",
                "system health summary",
            )
        ):
            return "service.status", {}

        if re.search(
            r"\b(unhealthy|health status|health states?|which .* healthy|which .* unhealthy)\b",
            normalized,
        ):
            return "docker.health_summary", {}

        container_name = extract_container_name(
            message
        )

        if container_name is not None:
            return "docker.inspect", {
                "container_name": container_name,
            }

        service = resolve_service(message)

        if service is not None:
            if service.get("scope") == "docker":
                return "network.reachability", {
                    "container": service["container"],
                    "port": service["port"],
                    "protocol": service.get(
                        "protocol",
                        "http",
                    ),
                    "path": service.get(
                        "health_path",
                        "/",
                    ),
                    "service_name": service["name"],
                }

            return "network.reachability", {
                "target": service["target"],
                "service_name": service["name"],
            }

        url = extract_url(message)

        if url is not None:
            return "network.reachability", {
                "target": url,
            }

        port = extract_port(message)

        if (
            port is not None
            and any(
                term in normalized
                for term in (
                    "reachable",
                    "reachability",
                    "connect",
                    "connectivity",
                )
            )
        ):
            return "network.reachability", {
                "host": "localhost",
                "port": port,
            }

        if port is not None:
            return "network.port_owner", {
                "port": port,
            }

        listener_terms = (
            "listening port",
            "listening ports",
            "listeners",
            "open port",
            "open ports",
            "what ports",
            "services listening",
        )

        if any(term in normalized for term in listener_terms):
            return "network.listeners", {}

        network_terms = (
            "network",
            "interface",
            "interfaces",
            "ip address",
            "ip addresses",
            "ethernet",
            "adapter",
            "adapters",
        )

        if any(term in normalized for term in network_terms):
            return "network.interfaces", {}

        return "docker.inventory", {}

    return None, {}


async def run_agent_tool(
    agent: AgentDefinition,
    message: str,
) -> tuple[str | None, dict | None]:
    tool_id, kwargs = select_tool(
        agent,
        message,
    )

    if tool_id is None:
        return None, None

    result = await execute_tool(
        tool_id,
        **kwargs,
    )

    return tool_id, result


def extract_container_name(
    message: str,
) -> str | None:
    normalized = message.strip()

    patterns = (
        r"\bcontainer\s+([A-Za-z0-9_.-]+)\b",
        r"\bdetails\s+for\s+([A-Za-z0-9_.-]+)\b",
        r"\bdoes\s+([A-Za-z0-9_.-]+)\s+expose\b",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    return None


def extract_url(message: str) -> str | None:
    match = re.search(
        r"https?://[^\s]+",
        message,
        re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(0).rstrip(".,);]}")


def extract_incident_hours(
    message: str,
) -> int | None:
    normalized = message.lower()

    match = re.search(
        r"\b(?:last|past)\s+(\d+)\s+(?:hours?|hrs?)\b",
        normalized,
        re.IGNORECASE,
    )

    if match:
        return max(
            1,
            min(int(match.group(1)), 168),
        )

    if (
        "last hour" in normalized
        or "past hour" in normalized
    ):
        return 1

    return None


def extract_incident_clock(
    message: str,
) -> tuple[int, int] | None:
    normalized = message.lower()

    match = re.search(
        r"\bsince\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        normalized,
        re.IGNORECASE,
    )

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3).lower()

        if not 1 <= hour <= 12:
            return None

        if not 0 <= minute <= 59:
            return None

        if meridiem == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12

        return hour, minute

    match = re.search(
        r"\bsince\s+([01]?\d|2[0-3]):([0-5]\d)\b",
        normalized,
        re.IGNORECASE,
    )

    if match:
        return (
            int(match.group(1)),
            int(match.group(2)),
        )

    return None


def extract_memory_query(
    message: str,
) -> str | None:
    text = message.strip()

    patterns = (
        r"^what do you remember about\s+(.+?)[?.!]*$",
        r"^what do you know about\s+(.+?)[?.!]*$",
        r"^search (?:your )?memory for\s+(.+?)[?.!]*$",
        r"^find (?:anything )?(?:you )?remember about\s+(.+?)[?.!]*$",
        r"^look in (?:your )?memory for\s+(.+?)[?.!]*$",
        r"^recall\s+(.+?)[?.!]*$",
    )

    for pattern in patterns:
        match = re.match(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            query = match.group(1).strip()

            return (
                query.rstrip("?.! ")
                or None
            )

    return None
