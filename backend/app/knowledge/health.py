"""Read-only local KB verification adapted from Agentic Stack kb_manage/kb_chunk."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.app.knowledge.retrieval import DEFAULT_REGISTRY, ROOT, TEXT_SUFFIXES


def inspect_kb(kb: dict, *, root: Path = ROOT) -> dict:
    result = {"id": kb.get("id"), "name": kb.get("name"),
              "enabled": kb.get("enabled") is True, "type": kb.get("type", "local_directory"),
              "path": kb.get("path"), "documents": 0, "chunks": 0,
              "hashes_checked": 0, "issues": [], "warnings": [], "issue_count": 0}

    def issue(message: str) -> None:
        result["issue_count"] += 1
        if len(result["issues"]) < 50:
            result["issues"].append(message)

    try:
        if not isinstance(kb.get("path"), str) or not kb["path"].strip():
            raise ValueError("Missing KB path")
        base = (root / kb["path"]).resolve()
        if not base.is_relative_to(root.resolve()):
            raise ValueError("KB path is outside the repository")
        if not base.is_dir():
            raise ValueError("KB directory is missing")
        kind = result["type"]
        if kind not in {"local_directory", "chunk_directory"}:
            raise ValueError("Unsupported KB type")
        paths = sorted(base.glob("*.json") if kind == "chunk_directory" else base.rglob("*"))
        seen = set()
        unhashed = 0
        for path in paths:
            if not path.is_file() or (kind == "local_directory" and path.suffix.lower() not in TEXT_SUFFIXES):
                continue
            if not path.resolve().is_relative_to(base):
                issue(f"{path.name}: file resolves outside KB directory")
                continue
            label = path.relative_to(base).as_posix()
            try:
                content = path.read_text(encoding="utf-8")
                if kind == "local_directory":
                    result["documents"] += 1
                    if not content.strip():
                        issue(f"{label}: empty document")
                    continue
                result["chunks"] += 1
                record = json.loads(content)
                if not isinstance(record, dict):
                    raise ValueError("chunk must be an object")
                required = ("chunk_id", "source_path", "section", "content")
                if any(not isinstance(record.get(key), str) or not record[key].strip() for key in required):
                    raise ValueError("missing chunk ID, source, section, or content")
                if record.get("kb") != kb.get("id"):
                    issue(f"{label}: KB identity mismatch")
                if record["chunk_id"] in seen:
                    issue(f"{label}: duplicate chunk ID")
                seen.add(record["chunk_id"])
                digest = record.get("sha256")
                if not digest:
                    unhashed += 1
                else:
                    # Match Agentic Stack's exact source + section + content hash.
                    payload = "\n".join(record[key] for key in ("source_path", "section", "content"))
                    expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                    result["hashes_checked"] += 1
                    if digest != expected:
                        issue(f"{label}: content/provenance hash mismatch")
            except (OSError, UnicodeError, ValueError) as exc:
                issue(f"{label}: {type(exc).__name__}: {exc}")
        if result["documents"] + result["chunks"] == 0:
            issue("No retrievable documents or chunks")
        if unhashed:
            result["warnings"].append(f"{unhashed} chunks have no integrity hash")
        if kind == "local_directory":
            result["warnings"].append("Local documents have no chunk integrity hashes")
    except (OSError, ValueError) as exc:
        issue(str(exc))
    result["status"] = "failed" if result["issue_count"] else "warning" if result["warnings"] else "ready"
    return result


def knowledge_health(*, registry_path: Path = DEFAULT_REGISTRY, root: Path = ROOT, kb_id: str | None = None) -> dict:
    report = {"scope": "local_reference_files", "remote_freshness": "not_checked",
              "notice": "Local integrity does not establish source authority, remote freshness, or live system state.",
              "registry_errors": [], "knowledge_bases": []}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entries = registry.get("knowledge_bases") if isinstance(registry, dict) else None
        if not isinstance(entries, list) or not entries:
            raise ValueError("Registry must contain a nonempty knowledge_bases list")
        ids = set()
        for kb in entries:
            if not isinstance(kb, dict) or not isinstance(kb.get("id"), str) or not kb["id"].strip():
                report["registry_errors"].append("Invalid KB registry entry")
                continue
            if kb["id"] in ids:
                report["registry_errors"].append(f"Duplicate KB ID: {kb['id']}")
            ids.add(kb["id"])
            if kb_id is None or kb["id"] == kb_id:
                report["knowledge_bases"].append(inspect_kb(kb, root=root))
        if kb_id is not None and kb_id not in ids:
            report["registry_errors"].append(f"Unknown KB: {kb_id}")
    except (OSError, UnicodeError, ValueError) as exc:
        report["registry_errors"].append(f"Registry unavailable or invalid: {exc}")
    report["ok"] = not report["registry_errors"] and not any(
        kb["status"] == "failed" and (kb["enabled"] or kb_id is not None)
        for kb in report["knowledge_bases"]
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local knowledge-base health")
    parser.add_argument("command", choices=("status", "verify"))
    parser.add_argument("kb", nargs="?", default="all")
    args = parser.parse_args(argv)
    report = knowledge_health(kb_id=None if args.kb == "all" else args.kb)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
