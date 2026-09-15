import json

import pytest

from backend.app.knowledge import retrieval

PROMPT = (
    "Using the Open WebUI knowledge base, explain how hybrid search works in RAG. "
    "Cite the source document or section, and label the answer as reference guidance "
    "rather than a live inspection."
)


@pytest.mark.parametrize("query", [PROMPT, "Explain hybrid search in Open WebUI RAG."])
def test_hybrid_search_beats_sync_and_hybrid_azure(tmp_path, monkeypatch, query):
    chunks = tmp_path / "chunks"
    chunks.mkdir()
    records = [
        ("azure", "Hybrid Azure configuration", "Hybrid Azure groups and sAMAccountName configuration.", "azure.mdx"),
        ("sync", "Knowledge Base Sync", "Knowledge base sync updates source documents and knowledge base content.", "sync.mdx"),
        ("pipeline", "Enhanced RAG Pipeline", "Hybrid search combines keyword and vector retrieval for RAG.", "features/chat-conversations/rag/index.md"),
        ("weight", "RAG_HYBRID_BM25_WEIGHT", "Controls the keyword weight in hybrid search.", "reference/env-configuration.mdx"),
        ("focused", "Focused Retrieval", "Hybrid search retrieves context using keyword and semantic search.", "features/workspace/knowledge.mdx"),
    ]
    for ident, section, content, path in records:
        (chunks / f"{ident}.json").write_text(json.dumps({"chunk_id": ident, "section": section, "content": content, "source_path": path}))
    # Use production KB ranking configuration, not a tuned test-only version.
    config = next(kb for kb in retrieval.load_registry()["knowledge_bases"] if kb["id"] == "open-webui")
    config = dict(config, path="chunks")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"knowledge_bases": [config]}))
    monkeypatch.setattr(retrieval, "ROOT", tmp_path)
    results = retrieval.retrieve_knowledge(query, registry_path=registry)
    assert {row["chunk_id"] for row in results} == {"pipeline", "weight", "focused"}
    assert results[0]["chunk_id"] == "pipeline"
    context = retrieval.format_knowledge_context(results)
    assert "features/chat-conversations/rag/index.md" in context
    assert "NOT LIVE SYSTEM EVIDENCE" in context


def test_selector_and_instructions_are_not_search_subject():
    assert retrieval.retrieval_subject(PROMPT) == "explain how hybrid search works in RAG"
    assert "rag" in retrieval.meaningful_words("RAG.")
    assert retrieval.retrieval_subject("How do I create a knowledge base?") == "How do I create a knowledge base?"


def test_phrase_requires_words_in_order_and_on_boundaries():
    assert retrieval.phrase_matches("hybrid search", "Hybrid Azure search", ["hybrid search"]) == 0
    assert retrieval.phrase_matches("hybrid search", "hybrid searching", ["hybrid search"]) == 0
    assert retrieval.phrase_matches("hybrid search", "ENABLE_RAG_HYBRID_SEARCH", ["hybrid search"]) == 1


def test_zero_limit_returns_nothing():
    assert retrieval.retrieve_knowledge(PROMPT, max_results=0) == []
