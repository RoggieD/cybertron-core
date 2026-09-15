"""Resolve immutable reference snapshots with a single atomic pointer read."""
from __future__ import annotations

import json
import re
from pathlib import Path


def runtime_dir(kb: dict, root: Path) -> Path:
    kb_id = kb.get("id", "")
    if not isinstance(kb_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", kb_id):
        raise ValueError("Invalid knowledge-base ID")
    path = (root / "data/knowledge-runtime" / kb_id).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Knowledge runtime path escapes repository")
    return path


def read_state(kb: dict, root: Path) -> dict:
    path = runtime_dir(kb, root) / "active.json"
    if not path.exists():
        return {"generation": "legacy", "previous": None}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("Invalid knowledge activation state")
    for key in ("generation", "previous"):
        value = state.get(key)
        if key == "previous" and value is None:
            continue
        if value != "legacy" and (not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value)):
            raise ValueError("Invalid knowledge generation")
    return state


def generation_dir(kb: dict, root: Path, generation: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", generation):
        raise ValueError("Invalid knowledge generation")
    base = runtime_dir(kb, root)
    path = (base / "versions" / generation).resolve()
    if not path.is_relative_to(base):
        raise ValueError("Knowledge generation escapes runtime directory")
    return path


def active_path(kb: dict, root: Path) -> Path:
    state = read_state(kb, root)
    if state["generation"] == "legacy":
        path = (root / kb["path"]).resolve()
    else:
        path = generation_dir(kb, root, state["generation"]) / "chunks"
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("KB path is outside the repository")
    return path
