import json

from backend.app.knowledge.retrieval import (
    format_knowledge_context,
    matching_kbs,
    retrieve_knowledge,
    score_fields,
)


def test_registry_triggers_only_matching_enabled_kb(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "version": 1,
        "knowledge_bases": [
            {"id": "juniper", "name": "Juniper", "enabled": True, "triggers": ["junos"]},
            {"id": "other", "name": "Other", "enabled": False, "triggers": ["junos"]},
        ],
    }))
    assert [kb["id"] for kb in matching_kbs("Junos routing", registry_path=registry)] == ["juniper"]


def test_section_match_outranks_content_only_match():
    query = {"routing"}
    section_score = score_fields(query, section="Routing", content="misc")
    content_score = score_fields(query, section="Overview", content="routing")
    assert section_score > content_score


def test_missing_kb_directory_fails_safe(tmp_path):
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({
        "version": 1,
        "knowledge_bases": [{
            "id": "missing", "name": "Missing", "enabled": True,
            "triggers": ["missingkb"], "type": "local_directory",
            "path": "data/knowledge/does-not-exist",
        }],
    }))
    assert retrieve_knowledge("missingkb topic", registry_path=registry) == []


def test_formatted_context_is_labeled_reference_not_live_evidence():
    text = format_knowledge_context([{
        "kb": "test", "name": "Test KB", "path": "guide.md",
        "score": 10, "content": "Reference configuration guidance.",
    }])
    assert text.startswith("REFERENCE KNOWLEDGE — NOT LIVE SYSTEM EVIDENCE")
    assert "verified tool" in text.lower()
