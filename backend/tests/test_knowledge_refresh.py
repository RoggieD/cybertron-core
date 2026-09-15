import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from backend.app.knowledge import refresh as lifecycle
from backend.app.knowledge.health import knowledge_health
from backend.app.knowledge.retrieval import retrieve_knowledge
from backend.app.knowledge.versions import active_path, generation_dir, read_state, runtime_dir


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "core"
    root.mkdir()
    chunks = root / "chunks"
    chunks.mkdir()
    record = {"kb": "test", "chunk_id": "old", "source_path": "old.md", "section": "Hybrid",
              "content": "Original hybrid reference"}
    record["sha256"] = hashlib.sha256("\n".join(record[k] for k in ("source_path", "section", "content")).encode()).hexdigest()
    (chunks / "old.json").write_text(json.dumps(record))
    kb = {"id": "test", "name": "Test", "type": "chunk_directory", "path": "chunks", "enabled": True,
          "triggers": ["hybrid"], "source_extensions": [".md", ".mdx"], "exclude_paths": ["excluded/"]}
    registry = root / "registry.json"
    registry.write_text(json.dumps({"knowledge_bases": [kb]}))
    source = tmp_path / "source"
    source.mkdir()
    (source / "rag.mdx").write_text("---\ntitle: Metadata\n---\n# Hybrid search\nNew hybrid reference with BM25.")
    import backend.app.knowledge.retrieval as retrieval
    monkeypatch.setattr(retrieval, "ROOT", root)
    return root, registry, kb, source


def run(setup, **kwargs):
    root, registry, kb, source = setup
    return lifecycle.refresh(kb["id"], root=root, registry_path=registry, source=source, **kwargs)


def test_check_apply_retrieve_health_unchanged_and_rollback(setup):
    root, registry, kb, _ = setup
    initial = active_path(kb, root)
    report = run(setup)
    assert report["status"] == "update_available" and not report["baseline_known"]
    assert active_path(kb, root) == initial
    report = run(setup, apply=True)
    assert report["status"] == "activated"
    selected = active_path(kb, root)
    assert selected != initial and (initial / "old.json").exists()
    results = retrieve_knowledge("hybrid", registry_path=registry)
    assert results[0]["path"] == "rag.mdx"
    assert "BM25" in results[0]["content"]
    health = knowledge_health(root=root, registry_path=registry)
    assert health["ok"]
    assert health["knowledge_bases"][0]["refresh"]["generation"] == report["generation"]
    assert "BM25" not in json.dumps(health)
    assert run(setup, apply=True)["status"] == "unchanged"
    assert active_path(kb, root) == selected
    lifecycle.rollback("test", root=root, registry_path=registry)
    assert active_path(kb, root) == initial
    assert retrieve_knowledge("hybrid", registry_path=registry)[0]["content"] == "Original hybrid reference"


def test_document_changes_and_pinned_reader_survive_activation(setup):
    root, registry, kb, source = setup
    run(setup, apply=True)
    pinned = active_path(kb, root)
    old_bytes = {p.name: p.read_bytes() for p in pinned.glob("*.json")}
    (source / "rag.mdx").write_text("# Hybrid search\nChanged hybrid guidance")
    (source / "added.md").write_text("# Added\nAnother hybrid reference")
    report = run(setup, apply=True)
    assert report["changes"] == {"added": 1, "changed": 1, "removed": 0}
    assert {p.name: p.read_bytes() for p in pinned.glob("*.json")} == old_bytes
    (source / "rag.mdx").unlink()
    assert run(setup)["changes"] == {"added": 0, "changed": 0, "removed": 1}
    lifecycle.rollback("test", root=root, registry_path=registry)
    assert active_path(kb, root) == pinned


@pytest.mark.parametrize("failure", ["empty", "invalid_utf8", "no_chunks", "acquisition", "activation", "corrupt_chunks"])
def test_failure_preserves_active_state(setup, monkeypatch, failure):
    root, registry, kb, source = setup
    run(setup, apply=True)
    state = read_state(kb, root)
    selected = active_path(kb, root)
    if failure == "empty":
        (source / "rag.mdx").write_text("")
    elif failure == "invalid_utf8":
        (source / "rag.mdx").write_bytes(b"\xff")
    elif failure == "no_chunks":
        (source / "rag.mdx").write_text("# Heading only")
    elif failure == "acquisition":
        def fail(*args):
            raise subprocess.TimeoutExpired("git", 180)
        monkeypatch.setattr(lifecycle, "acquire_source", fail)
    elif failure == "activation":
        (source / "rag.mdx").write_text("# Hybrid\nChanged body")
        original = lifecycle.atomic_json
        def fail(path, value):
            if path.name == "active.json":
                raise OSError("simulated activation failure")
            original(path, value)
        monkeypatch.setattr(lifecycle, "atomic_json", fail)
    else:
        original = lifecycle.chunk_document
        def corrupt(*args):
            records = original(*args)
            for path in args[-1].glob("*.json"):
                data = json.loads(path.read_text())
                data["content"] = "tampered"
                path.write_text(json.dumps(data))
            return records
        monkeypatch.setattr(lifecycle, "chunk_document", corrupt)
    report = run(setup, apply=True)
    assert report["status"] == "failed" and not report["activated"]
    assert read_state(kb, root) == state
    assert active_path(kb, root) == selected
    assert "BM25" in retrieve_knowledge("hybrid", registry_path=registry)[0]["content"]


def test_lock_and_invalid_previous_snapshot(setup):
    root, registry, kb, source = setup
    run(setup, apply=True)
    first = active_path(kb, root)
    (source / "rag.mdx").write_text("# Hybrid\nUpdated")
    run(setup, apply=True)
    state = read_state(kb, root)
    next(first.glob("*.json")).write_text("{}")
    with pytest.raises(ValueError, match="manifest mismatch"):
        lifecycle.rollback("test", root=root, registry_path=registry)
    assert read_state(kb, root) == state
    with lifecycle.writer_lock(runtime_dir(kb, root)):
        with pytest.raises(ValueError, match="lock"):
            run(setup, apply=True)


def test_exclusions_posix_provenance_and_manifest_hashes(setup):
    root, _, kb, source = setup
    (source / "excluded").mkdir()
    (source / "excluded/bad.md").write_bytes(b"\xff")
    (source / "nested").mkdir()
    (source / "nested/guide.md").write_text("# Hybrid\nNested reference")
    report = run(setup, apply=True)
    assert report["status"] == "activated" and report["documents"] == 2
    version = generation_dir(kb, root, report["generation"])
    manifest = lifecycle.validate_snapshot(kb, root, version)
    assert "nested/guide.md" in manifest["files"]
    assert all("\\" not in json.loads(p.read_text())["source_path"] for p in (version / "chunks").glob("*.json"))


def test_git_source_is_pinned_to_checked_out_commit(setup, monkeypatch):
    root, registry, kb, source = setup
    kb["source_refresh"] = {"type": "git", "repository": "https://example.test/docs.git", "branch": "main", "subdirectory": "docs"}
    registry.write_text(json.dumps({"knowledge_bases": [kb]}))
    calls = []
    def fake_git(*args):
        calls.append(args)
        if args[0] == "clone":
            docs = Path(args[-1]) / "docs"
            docs.mkdir(parents=True)
            (docs / "guide.md").write_text("# Hybrid\nRemote reference")
            return ""
        return "a" * 40
    monkeypatch.setattr(lifecycle, "git", fake_git)
    report = lifecycle.refresh("test", root=root, registry_path=registry, apply=True)
    assert report["status"] == "activated"
    assert report["source"]["commit"] == "a" * 40
    assert calls[1][-2:] == ("rev-parse", "HEAD")


def test_invalid_identity_and_state_path_are_rejected(setup):
    root, registry, kb, _ = setup
    with pytest.raises(ValueError):
        runtime_dir({"id": "../../outside"}, root)
    base = runtime_dir(kb, root)
    base.mkdir(parents=True)
    (base / "active.json").write_text(json.dumps({"generation": "../outside"}))
    assert run(setup, apply=True)["status"] == "failed"
