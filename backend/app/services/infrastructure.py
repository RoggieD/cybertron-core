"""A bounded, evidence-backed infrastructure snapshot, independent of chat."""
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from backend.app.events.schema import CoreEvent
from backend.app.tools.registry import execute_tool
from backend.app.traces.store import trace_store


def now():
    return datetime.now(timezone.utc).isoformat()


def identity(kind, value):
    return f"{kind}:{sha256(str(value).encode()).hexdigest()[:20]}"


def project(observations, trace_id):
    nodes, edges = [], []
    omitted = 0

    def node(kind, key, label, state, details, source):
        item = {"id": identity(kind, key), "kind": kind, "label": label,
                "state": state, "details": details, "source": source,
                "observed_at": observations[source]["finished_at"], "trace_id": trace_id}
        nodes.append(item)
        return item["id"]

    def edge(source, target, relation, basis):
        edges.append({"source": source, "target": target, "relation": relation, "basis": basis})

    host = observations["system.snapshot"].get("result", {})
    host_id = None
    if host.get("hostname"):
        host_id = node("host", host["hostname"], host["hostname"], "observed", host, "system.snapshot")

    docker = observations["docker.inventory"].get("result", {})
    containers = {}
    if docker.get("available"):
        engine = node("engine", "configured-docker-endpoint", "Docker endpoint", "responding",
                      {"notice": "Endpoint selected by the backend Docker CLI. Host placement is not inferred."}, "docker.inventory")
        if host_id:
            edge(host_id, engine, "QUERIES", "Backend Docker CLI inventory")
        rows = docker.get("containers") or []
        omitted += max(0, len(rows) - 200)
        for item in rows[:200]:
            key = item.get("ID") or item.get("Names")
            if not key:
                continue
            name = str(item.get("Names") or key)
            details = {k: item[k] for k in ("ID", "Names", "Image", "State", "Status", "Ports", "Networks") if k in item}
            container = node("container", key, name, str(item.get("State") or "unknown"), details, "docker.inventory")
            containers[name] = container
            edge(engine, container, "INVENTORIES", "docker.inventory returned this container")

    services = observations["service.status"].get("result", {}).get("services") or []
    omitted += max(0, len(services) - 100)
    for item in services[:100]:
        name = str(item.get("name") or "Unnamed service")
        key = (name, item.get("container"), item.get("container_port")) if item.get("container") else (name, item.get("target_configured") or item.get("target"))
        details = {k: v for k, v in item.items() if k in {
            "scope", "target", "target_configured", "status_code", "reason", "latency_ms", "error",
            "container", "container_port", "container_status", "container_health", "image", "networks"}}
        service = node("service", key, name, "reachable" if item.get("reachable") else "check failed", details, "service.status")
        if host_id:
            edge(host_id, service, "PROBES", "Reachability measured from the backend; not proof of deployment location")
        container = containers.get(item.get("container"))
        if container and item.get("container_status"):
            edge(container, service, "SERVICE_TARGET", "Service check inspected this named container")
    return {"nodes": nodes, "edges": edges, "omitted": omitted}


async def infrastructure_snapshot():
    trace_id = str(uuid4())
    started = now()

    async def inspect(tool):
        start = now()
        try:
            result = await asyncio.wait_for(execute_tool(tool), timeout=25)
            error = (result.get("error") or "Source unavailable") if result.get("available") is False else None
            return tool, {"started_at": start, "finished_at": now(), "error": error, "result": result}
        except Exception as exc:
            return tool, {"started_at": start, "finished_at": now(), "error": str(exc) or type(exc).__name__, "result": {}}

    observations = dict(await asyncio.gather(*(inspect(tool) for tool in (
        "system.snapshot", "docker.inventory", "service.status"))))
    snapshot = {"trace_id": trace_id, "started_at": started, "finished_at": now(),
                "scope": "backend_observation", "sources": [
                    {"tool": tool, **{k: v for k, v in obs.items() if k != "result"}}
                    for tool, obs in observations.items()], **project(observations, trace_id)}
    # Persist the bounded projection for audit, without broadcasting an unrelated
    # graph refresh into the active conversation or capturing it as a chat episode.
    await trace_store.save(CoreEvent(event_type="infrastructure.snapshot", trace_id=trace_id,
                                    actor={"type": "ui", "id": "infrastructure-explorer"},
                                    status="partial" if any(o["error"] for o in observations.values()) else "complete",
                                    metadata=snapshot))
    return snapshot
