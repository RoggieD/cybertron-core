import asyncio
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.services import infrastructure as graph
from backend.app.traces.store import TraceStore


def observations(docker=None):
    results = {
        "system.snapshot": {"hostname": "test-host", "cpu": {"usage_percent": 5}},
        "docker.inventory": docker or {"available": True, "containers": [{"ID": "abc", "Names": "voice", "State": "running", "Image": "voice:v1"}]},
        "service.status": {"services": [
            {"name": "Voice", "container": "voice", "container_status": "running", "reachable": True},
            {"name": "External", "target": "https://example.test", "reachable": False, "error": "timeout"},
        ]},
    }
    return {key: {"result": result, "started_at": "2026-09-15T00:00:00Z", "finished_at": "2026-09-15T00:00:01Z", "error": None} for key, result in results.items()}


def test_graph_links_only_evidenced_relationships_and_preserves_provenance():
    result = graph.project(observations(), "trace-1")
    assert len(result["nodes"]) == 5
    assert {e["relation"] for e in result["edges"]} == {"QUERIES", "INVENTORIES", "PROBES", "SERVICE_TARGET"}
    assert all(n["trace_id"] == "trace-1" and n["observed_at"] for n in result["nodes"])
    failed = next(n for n in result["nodes"] if n["label"] == "External")
    assert failed["state"] == "check failed"
    assert failed["details"]["error"] == "timeout"
    # No invented host-to-container deployment edges, even for a local Docker CLI.
    kinds = {n["id"]: n["kind"] for n in result["nodes"]}
    assert not any(kinds[e["source"]] == "host" and kinds[e["target"]] == "container" for e in result["edges"])


def test_unavailable_docker_does_not_invent_containers_or_links():
    result = graph.project(observations({"available": False, "error": "denied"}), "trace")
    assert not any(n["kind"] in {"container", "engine"} for n in result["nodes"])
    assert not any(e["relation"] == "SERVICE_TARGET" for e in result["edges"])


def test_snapshot_limit_and_stable_ids():
    obs = observations({"available": True, "containers": [{"ID": str(i), "Names": f"c{i}"} for i in range(250)]})
    first, second = graph.project(obs, "first"), graph.project(obs, "second")
    assert first["omitted"] == 50
    assert [n["id"] for n in first["nodes"]] == [n["id"] for n in second["nodes"]]
    ids = {n["id"] for n in first["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in first["edges"])


def test_endpoint_retains_successful_sources_and_saves_inspection_trace(monkeypatch, tmp_path):
    from backend.app.api.status import router
    store = TraceStore(str(tmp_path / "traces.db"))
    results = observations()

    async def execute(tool):
        if tool == "docker.inventory":
            raise RuntimeError("Docker unavailable")
        return results[tool]["result"]

    monkeypatch.setattr(graph, "execute_tool", execute)
    monkeypatch.setattr(graph, "trace_store", store)
    app = FastAPI(); app.include_router(router)
    response = TestClient(app).get("/api/status/infrastructure")
    assert response.status_code == 200
    snapshot = response.json()
    assert any(n["kind"] == "host" for n in snapshot["nodes"])
    assert snapshot["sources"][1]["error"] == "Docker unavailable"
    events = asyncio.run(store.by_trace(snapshot["trace_id"], 10))
    assert len(events) == 1
    assert events[0]["event_type"] == "infrastructure.snapshot"
    assert events[0]["status"] == "partial"
    assert events[0]["metadata"]["nodes"] == snapshot["nodes"]
    summary = asyncio.run(store.recent_trace_summaries(10))[0]
    assert summary["completed"] == 1
