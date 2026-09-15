import hashlib
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.knowledge.health import inspect_kb, knowledge_health, main


def chunk(tmp_path, **updates):
    record = dict(kb="test", chunk_id="one", source_path="docs/a.md", section="Setup", content="Private source text")
    record["sha256"] = hashlib.sha256("\n".join(record[key] for key in ("source_path", "section", "content")).encode()).hexdigest()
    record.update(updates)
    folder = tmp_path / "chunks"
    folder.mkdir(exist_ok=True)
    (folder / "one.json").write_text(json.dumps(record), encoding="utf-8")
    return {"id": "test", "enabled": True, "type": "chunk_directory", "path": "chunks"}


def test_valid_chunk_hash_and_read_only(tmp_path):
    kb = chunk(tmp_path)
    before = (tmp_path / "chunks/one.json").read_bytes()
    report = inspect_kb(kb, root=tmp_path)
    assert report["status"] == "ready"
    assert report["chunks"] == report["hashes_checked"] == 1
    assert "Private source text" not in json.dumps(report)
    assert (tmp_path / "chunks/one.json").read_bytes() == before


@pytest.mark.parametrize("updates,issue", [({"content": "changed"}, "hash mismatch"),
    ({"kb": "wrong"}, "identity mismatch"), ({"source_path": ""}, "missing chunk")])
def test_invalid_chunks_fail(tmp_path, updates, issue):
    result = inspect_kb(chunk(tmp_path, **updates), root=tmp_path)
    assert result["status"] == "failed"
    assert issue in " ".join(result["issues"])


def test_missing_hash_is_warning(tmp_path):
    result = inspect_kb(chunk(tmp_path, sha256=None), root=tmp_path)
    assert result["status"] == "warning"
    assert result["hashes_checked"] == 0


def test_duplicates_and_invalid_json(tmp_path):
    kb = chunk(tmp_path)
    (tmp_path / "chunks/two.json").write_bytes((tmp_path / "chunks/one.json").read_bytes())
    (tmp_path / "chunks/bad.json").write_text("{broken")
    result = inspect_kb(kb, root=tmp_path)
    assert result["status"] == "failed"
    assert result["issue_count"] == 2


def test_missing_and_outside_paths(tmp_path):
    for path in ("missing", "../outside"):
        assert inspect_kb({"id": "x", "path": path}, root=tmp_path)["status"] == "failed"


def test_document_inventory_and_empty_file(tmp_path):
    (tmp_path / "guide.md").write_text("Guide")
    kb = {"id": "local", "path": ".", "type": "local_directory"}
    result = inspect_kb(kb, root=tmp_path)
    assert result["documents"] == 1
    assert result["status"] == "warning"
    (tmp_path / "empty.txt").write_text("")
    assert inspect_kb(kb, root=tmp_path)["status"] == "failed"


def test_registry_missing_invalid_duplicate_and_disabled(tmp_path):
    registry = tmp_path / "registry.json"
    assert not knowledge_health(registry_path=registry, root=tmp_path)["ok"]
    registry.write_text("[]")
    assert not knowledge_health(registry_path=registry, root=tmp_path)["ok"]
    kb = {"id": "missing", "path": "missing", "enabled": False}
    registry.write_text(json.dumps({"knowledge_bases": [kb]}))
    assert knowledge_health(registry_path=registry, root=tmp_path)["ok"]
    assert not knowledge_health(registry_path=registry, root=tmp_path, kb_id="missing")["ok"]
    assert not knowledge_health(registry_path=registry, root=tmp_path, kb_id="unknown")["ok"]
    registry.write_text(json.dumps({"knowledge_bases": [kb, kb]}))
    assert not knowledge_health(registry_path=registry, root=tmp_path)["ok"]


def test_cli_exit_and_read_only_api(monkeypatch, capsys):
    import importlib
    health = importlib.import_module("backend.app.knowledge.health")
    api = importlib.import_module("backend.app.api.knowledge")
    report = {"ok": False, "remote_freshness": "not_checked"}
    monkeypatch.setattr(health, "knowledge_health", lambda **kw: report)
    assert main(["verify", "all"]) == 1
    assert json.loads(capsys.readouterr().out) == report
    monkeypatch.setattr(api, "knowledge_health", lambda: report)
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        assert client.get("/api/knowledge/status").json() == report
        assert client.post("/api/knowledge/status").status_code == 405
