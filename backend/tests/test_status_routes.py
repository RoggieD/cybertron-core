from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.status import router
from backend.app.telemetry import incidents


def test_incident_collection_routes_are_not_treated_as_ids(monkeypatch):
    monkeypatch.setattr(incidents, "incident_analytics", lambda: {"total_events": 7})
    monkeypatch.setattr(incidents, "search_incidents", lambda **kw: [{"id": "cpu", "duration_seconds": 3}])
    monkeypatch.setattr(incidents, "incident_timeline", lambda incident_id: {"incident_id": incident_id})
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/status/incidents/analytics").json() == {"total_events": 7}
    assert client.get("/api/status/incidents/search?q=cpu").json()["incidents"][0]["id"] == "cpu"
    response = client.get("/api/status/incidents/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "cpu" in response.text
    assert client.get("/api/status/incidents/cpu").json() == {"incident_id": "cpu"}


def test_frontend_probe_uses_configured_url_and_ca(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from backend.app.tools import services

    probe = AsyncMock(return_value={"reachable": False, "error": "certificate mismatch"})
    monkeypatch.setattr(services, "network_reachability", probe)
    result = asyncio.run(services._check_service({
        "name": "Frontend", "target": "https://localhost:5173", "ca_file": "certs/local.pem",
    }))
    probe.assert_awaited_once_with(target="https://localhost:5173", ca_file="certs/local.pem", service_name="Frontend")
    assert not result["reachable"]
    assert result["error"] == "certificate mismatch"


def test_https_probe_trusts_local_ca_without_disabling_verification(monkeypatch, tmp_path):
    import asyncio
    import ssl
    from unittest.mock import MagicMock
    from backend.app.tools import reachability

    cert = tmp_path / "local.pem"
    cert.write_text("test certificate")
    context = MagicMock(spec=ssl.SSLContext)
    monkeypatch.setattr(reachability.ssl, "create_default_context", lambda: context)
    seen = {}

    class Client:
        def __init__(self, **kwargs): seen.update(kwargs)
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url):
            raise RuntimeError("certificate hostname mismatch")

    monkeypatch.setattr(reachability.httpx, "AsyncClient", Client)
    result = asyncio.run(reachability._check_http("https://localhost:5173", ca_file=str(cert)))
    context.load_verify_locations.assert_called_once_with(cafile=str(cert))
    assert seen["verify"] is context
    assert result["reachable"] is False
    assert "hostname mismatch" in result["error"]
