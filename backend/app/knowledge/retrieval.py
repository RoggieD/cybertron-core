from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.memory.context_budget import allocate_context_budget, trim_to_token_budget

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = ROOT / "data" / "knowledge" / "registry.json"
TEXT_SUFFIXES = {".md", ".txt", ".rst", ".json", ".yaml", ".yml"}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "i", "in", "is", "it", "my", "of", "on", "or", "the", "to", "with",
}
NORMALIZE = {
    "troubleshoot": "troubleshoot",
    "troubleshoots": "troubleshoot",
    "troubleshooting": "troubleshoot",
    "troubleshot": "troubleshoot",
    "configure": "config",
    "configuration": "config",
    "configurations": "config",
    "configured": "config",
    "configuring": "config",
    "route": "routing",
    "routes": "routing",
    "router": "routing",
    "policies": "policy",
    "interfaces": "interface",
    "firewalls": "firewall",
}


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_.:-]+", text.lower()))


def normalize_word(word: str) -> str:
    return NORMALIZE.get(word, word)


def meaningful_words(text: str) -> set[str]:
    return {
        normalize_word(word)
        for word in words(text)
        if word not in STOPWORDS and len(word) > 1
    }


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "knowledge_bases": []}
    return json.loads(path.read_text(encoding="utf-8"))


def matching_kbs(query: str, *, registry_path: Path = DEFAULT_REGISTRY) -> list[dict]:
    lowered = query.lower()
    return [
        kb for kb in load_registry(registry_path).get("knowledge_bases", [])
        if kb.get("enabled", False)
        and any(str(trigger).lower() in lowered for trigger in kb.get("triggers", []))
    ]


def score_fields(
    query_words: set[str], *, query_text: str = "", source_path: str = "",
    section: str = "", content: str = "", score_phrases=None,
    score_term_weights=None,
) -> int:
    if not query_words:
        return 0

    path_words = meaningful_words(re.sub(r"[\\/_.-]+", " ", source_path))
    section_words = meaningful_words(section)
    content_words = meaningful_words(content)
    term_weights = {
        normalize_word(str(term).lower()): int(weight)
        for term, weight in (score_term_weights or {}).items()
    }
    score = 0

    for word in query_words:
        weight = term_weights.get(word, 1)
        if word in section_words:
            score += 5 * weight
        if word in path_words:
            score += 3 * weight
        if word in content_words:
            score += weight

    query_lower = query_text.lower().strip()
    section_lower = section.lower().strip()
    content_lower = content.lower()
    phrases = list(score_phrases or [])

    for phrase in phrases:
        phrase = str(phrase).lower().strip()
        if not phrase or phrase not in query_lower:
            continue
        if section_lower == phrase or section_lower.startswith(phrase):
            score += 10
        elif phrase in section_lower:
            score += 3
        elif phrase in content_lower:
            score += 1

    if "troubleshoot" in meaningful_words(query_text) and "troubleshoot" in section_words:
        score += 10

    return score


def _kb_base(kb: dict) -> Path:
    return ROOT / str(kb["path"])


def _retrieve_directory(kb: dict, query_words: set[str], query: str) -> list[dict]:
    base = _kb_base(kb)
    if not base.exists():
        return []
    results = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        score = score_fields(
            query_words, query_text=query, source_path=str(path), content=text,
            score_phrases=kb.get("score_phrases", []),
            score_term_weights=kb.get("score_term_weights", {}),
        )
        if score > 0:
            results.append({
                "kb": kb["id"], "name": kb["name"],
                "path": str(path.relative_to(ROOT)), "score": score,
                "content": text[:4000],
            })
    return results


def _retrieve_chunks(kb: dict, query_words: set[str], query: str) -> list[dict]:
    base = _kb_base(kb)
    if not base.exists():
        return []
    results = []
    for path in sorted(base.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        content = record.get("content", "")
        source_path = record.get("source_path", "")
        section = record.get("section", "")
        score = score_fields(
            query_words, query_text=query, source_path=source_path,
            section=section, content=content,
            score_phrases=kb.get("score_phrases", []),
            score_term_weights=kb.get("score_term_weights", {}),
        )
        if score > 0:
            results.append({
                "kb": kb["id"], "name": kb["name"], "path": source_path,
                "section": section, "chunk_id": record.get("chunk_id"),
                "score": score, "content": content,
            })
    return results


def retrieve_knowledge(
    query: str, *, max_results: int = 3, registry_path: Path = DEFAULT_REGISTRY,
) -> list[dict]:
    base_words = meaningful_words(query)
    results = []
    for kb in matching_kbs(query, registry_path=registry_path):
        ignored = {normalize_word(str(t).lower()) for t in kb.get("score_ignore_terms", [])}
        query_words = {word for word in base_words if word not in ignored}
        if kb.get("type", "local_directory") == "chunk_directory":
            results.extend(_retrieve_chunks(kb, query_words, query))
        else:
            results.extend(_retrieve_directory(kb, query_words, query))
    results.sort(key=lambda item: (-item["score"], item.get("path", ""), item.get("section", "")))
    return results[:max_results]


def format_knowledge_context(results: list[dict]) -> str:
    if not results:
        return ""
    lines = [
        "REFERENCE KNOWLEDGE — NOT LIVE SYSTEM EVIDENCE",
        "Use this material as documentation/reference context only.",
        "Do not describe it as a live observation unless a verified tool independently confirms it.",
    ]
    for result in results:
        label = result.get("section") or result.get("path") or "reference"
        lines.extend([
            "",
            f"[{result.get('name', result.get('kb', 'Knowledge Base'))}] {label}",
            result.get("content", ""),
        ])
    context = "\n".join(lines)
    budget = allocate_context_budget()["knowledge"]
    return trim_to_token_budget(context, budget, keep="start")
