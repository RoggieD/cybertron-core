"""Explicit reference refresh: stage, hash, chunk, verify, atomically activate."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from backend.app.knowledge.chunking import chunk_document
from backend.app.knowledge.health import inspect_kb
from backend.app.knowledge.retrieval import DEFAULT_REGISTRY, ROOT, load_registry
from backend.app.knowledge.versions import generation_dir, read_state, runtime_dir

NOTICE = "Reference maintenance only; source integrity does not establish authority or live system state."


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def writer_lock(base: Path):
    base.mkdir(parents=True, exist_ok=True)
    lock = base / "refresh.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("A refresh lock exists; another writer may be active") from None
    try:
        with handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def get_kb(kb_id: str, registry_path: Path) -> dict:
    matches = [kb for kb in load_registry(registry_path).get("knowledge_bases", []) if kb.get("id") == kb_id]
    if len(matches) != 1:
        raise ValueError("KB must have exactly one registry entry")
    kb = matches[0]
    if kb.get("type") != "chunk_directory":
        raise ValueError("Refresh requires a chunk_directory knowledge base")
    return kb


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, timeout=180,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if result.returncode:
        raise ValueError("Git source acquisition failed; active references were not changed")
    return result.stdout.strip()


def acquire_source(kb: dict, stage: Path, source: Path | None) -> tuple[Path, dict]:
    if source is not None:
        return source.resolve(strict=True), {"type": "local", "remote_freshness": "not_checked"}
    config = kb.get("source_refresh", {})
    repository = config.get("repository", "")
    branch = config.get("branch", "main")
    subdir = Path(config.get("subdirectory", ""))
    if config.get("type") != "git" or not repository.startswith("https://"):
        raise ValueError("Configure an HTTPS Git source or provide --source")
    if not isinstance(branch, str) or branch.startswith("-") or not branch.strip():
        raise ValueError("Invalid source branch")
    if subdir.is_absolute() or ".." in subdir.parts:
        raise ValueError("Invalid source subdirectory")
    checkout = stage / "checkout"
    git("clone", "--depth", "1", "--single-branch", "--branch", branch, "--", repository, str(checkout))
    source_root = (checkout / subdir).resolve(strict=True)
    if not source_root.is_relative_to(checkout.resolve()):
        raise ValueError("Source subdirectory escapes checkout")
    return source_root, {"type": "git", "repository": repository, "branch": branch,
                         "commit": git("-C", str(checkout), "rev-parse", "HEAD"),
                         "remote_freshness": "fetched_at_refresh_time"}


def source_files(kb: dict, source: Path) -> dict[str, bytes]:
    if not source.is_dir():
        raise ValueError("Source must be a document directory")
    extensions = set(kb.get("source_extensions", [".md", ".mdx", ".txt"]))
    excluded = kb.get("exclude_paths", [])
    files = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlinks are not accepted in refresh sources")
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        relative = path.relative_to(source).as_posix()
        if any(relative.startswith(p) if p.endswith("/") else relative == p for p in excluded):
            continue
        data = path.read_bytes()
        if not data.decode("utf-8").strip():
            raise ValueError(f"Empty reference document: {relative}")
        files[relative] = data
    if not files:
        raise ValueError("No eligible source documents; refusing an empty replacement")
    return files


def hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def validate_snapshot(kb: dict, root: Path, version: Path) -> dict:
    manifest = json.loads((version / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("kb") != kb["id"]:
        raise ValueError("Snapshot KB identity mismatch")
    for directory, field in (("source", "files"), ("chunks", "chunk_files")):
        actual = {}
        base = version / directory
        for path in base.rglob("*"):
            if path.is_symlink() or not path.resolve().is_relative_to(version.resolve()):
                raise ValueError("Snapshot contains an unsafe path")
            if path.is_file():
                actual[path.relative_to(base).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if not actual or actual != manifest.get(field):
            raise ValueError(f"Snapshot {directory} manifest mismatch")
    report = inspect_kb({**kb, "path": str(version / "chunks")}, root=root, use_active=False)
    if report["status"] != "ready":
        raise ValueError("Staged chunk verification failed: " + "; ".join(report["issues"]))
    return manifest


def refresh(kb_id: str, *, source: Path | None = None, apply: bool = False,
            registry_path: Path = DEFAULT_REGISTRY, root: Path = ROOT) -> dict:
    kb = get_kb(kb_id, registry_path)
    if not kb.get("enabled"):
        raise ValueError("Cannot refresh a disabled knowledge base")
    base = runtime_dir(kb, root)
    with writer_lock(base):
        report = {"kb": kb_id, "notice": NOTICE, "status": "failed", "activated": False}
        try:
            before = read_state(kb, root)
            generation = uuid4().hex
            stage = generation_dir(kb, root, generation)
            stage.mkdir(parents=True)
            upstream, provenance = acquire_source(kb, stage, source)
            # Read once, then chunk the copied bytes so the manifest describes
            # the exact input even if a local source changes during the refresh.
            files = source_files(kb, upstream)
            for relative, data in files.items():
                target = stage / "source" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            chunks = stage / "chunks"
            chunks.mkdir()
            for relative in files:
                if not chunk_document(kb_id, stage / "source" / relative, stage / "source", chunks):
                    raise ValueError(f"Document produced no usable chunks: {relative}")
            manifest = {"kb": kb_id, "created_at": datetime.now(timezone.utc).isoformat(),
                        "source": provenance, "files": hashes(files),
                        "chunk_files": hashes({p.name: p.read_bytes() for p in chunks.glob("*.json")})}
            atomic_json(stage / "manifest.json", manifest)
            validate_snapshot(kb, root, stage)
            old_files = {}
            old_manifest = {}
            if before["generation"] != "legacy":
                old_manifest = validate_snapshot(kb, root, generation_dir(kb, root, before["generation"]))
                old_files = old_manifest["files"]
            changes = {
                "added": len(manifest["files"].keys() - old_files.keys()),
                "changed": sum(old_files[name] != digest for name, digest in manifest["files"].items() if name in old_files),
                "removed": len(old_files.keys() - manifest["files"].keys()),
            }
            report.update(source=provenance, changes=changes, baseline_known=before["generation"] != "legacy",
                          documents=len(files), chunks=len(manifest["chunk_files"]), generation=generation)
            same = (before["generation"] != "legacy" and not any(changes.values())
                    and manifest["chunk_files"] == old_manifest.get("chunk_files"))
            report["status"] = "unchanged" if same else "update_available"
            if apply and not same:
                if read_state(kb, root) != before:
                    raise ValueError("Active knowledge changed during refresh")
                state = {"generation": generation, "previous": before["generation"],
                         "activated_at": datetime.now(timezone.utc).isoformat()}
                # This is the only mutation that changes what retrieval reads.
                atomic_json(base / "active.json", state)
                report.update(status="activated", activated=True)
            return report
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report.update(status="failed", error=str(exc))
            return report
        finally:
            # Failure to record an attempt must not turn successful activation
            # into a claimed failure or corrupt its independently committed state.
            try:
                atomic_json(base / "last-refresh.json", {**report, "checked_at": datetime.now(timezone.utc).isoformat()})
            except OSError:
                pass


def rollback(kb_id: str, *, registry_path: Path = DEFAULT_REGISTRY, root: Path = ROOT) -> dict:
    kb = get_kb(kb_id, registry_path)
    base = runtime_dir(kb, root)
    with writer_lock(base):
        before = read_state(kb, root)
        previous = before.get("previous")
        if previous is None:
            raise ValueError("No previous version is recorded")
        if previous == "legacy":
            report = inspect_kb(kb, root=root, use_active=False)
            if report["status"] != "ready":
                raise ValueError("Original chunks failed validation; rollback not activated")
        else:
            validate_snapshot(kb, root, generation_dir(kb, root, previous))
        atomic_json(base / "active.json", {"generation": previous, "previous": before["generation"],
                                          "activated_at": datetime.now(timezone.utc).isoformat()})
        return {"kb": kb_id, "status": "rolled_back", "generation": previous, "notice": NOTICE}


def refresh_status(kb: dict, root: Path) -> dict:
    try:
        state = read_state(kb, root)
        path = runtime_dir(kb, root) / "last-refresh.json"
        attempt = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        active_source = None
        if state["generation"] != "legacy":
            manifest = generation_dir(kb, root, state["generation"]) / "manifest.json"
            active_source = json.loads(manifest.read_text(encoding="utf-8")).get("source")
        return {"scope": "reference_maintenance", "generation": state["generation"],
                "active_source": active_source,
                "previous": state.get("previous"), "last_attempt": attempt,
                "remote_freshness": "not_checked_now"}
    except (OSError, ValueError) as exc:
        return {"scope": "reference_maintenance", "status": "failed", "error": str(exc)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=NOTICE)
    parser.add_argument("command", choices=("check", "apply", "rollback"))
    parser.add_argument("kb")
    parser.add_argument("--source", type=Path, help="Read local source documents instead of configured Git source")
    args = parser.parse_args(argv)
    try:
        if args.command == "rollback":
            if args.source is not None:
                parser.error("rollback does not accept --source")
            report = rollback(args.kb)
        else:
            report = refresh(args.kb, source=args.source, apply=args.command == "apply")
    except (OSError, ValueError) as exc:
        report = {"status": "failed", "error": str(exc), "notice": NOTICE}
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
