# Local knowledge-base health

C.O.R.E. now has the read-only status/verify portion of Agentic Stack's KB
lifecycle workflow. It uses C.O.R.E.'s existing registry and supports local
documents and chunk directories. No source refresh, rebuild, or rollback occurs.

Run from the repository root on GM-AI01:

```bash
.venv/bin/python -m backend.app.knowledge.health status
.venv/bin/python -m backend.app.knowledge.health verify juniper
```

Both commands return JSON. Exit 1 means a registry error or failed enabled KB;
explicit verification of a disabled KB also fails if that KB is broken.
Disabled KB failures remain visible in the inventory without failing `all`.
`GET /api/knowledge/status` exposes the same report (HTTP 200 with `ok: false`
when local integrity checks fail).

Checks cover missing/empty directories, unsupported types, invalid chunk JSON,
required source fields, duplicate chunk IDs, KB identity, and optional hashes.
Hashes use Agentic Stack's exact `source_path + newline + section + newline +
content` SHA-256 convention. Missing hashes produce warnings, never an integrity
claim. Error details are capped at 50 per KB; issue_count reports the full count.

`ready` means local structural/hash checks passed. It does not prove reference
accuracy, upstream freshness, or any live infrastructure state. Remote freshness
is explicitly `not_checked`. Raw document content is not included in the report.
This initial module does not change retrieval or automatically disable sources.

## Retrieval ranking

Reference retrieval uses the full request to select enabled KBs, then removes
an initial `Using the … knowledge base,` selector and trailing citation instructions
from the ranking topic. Configured compound phrases (for example `hybrid search`)
rank ahead of isolated-word matches, followed by existing weighted term scores.
Phrase matching respects token order and boundaries and recognizes underscores
in documented setting names. Sentence-ending punctuation no longer hides terms
such as `RAG.` from their configured weights. Model context includes source paths
and chunk IDs alongside the existing reference-only evidence label.

Reference implementation: `RoggieD/cybertron-agentic-stack`,
`.agent/tools/kb_manage.py` (status/verify) and `.agent/tools/kb_chunk.py` (hash format).


## Processing Graph reference provenance

Reference retrieval now emits `knowledge.search_started`, `knowledge.search_completed`,
and `knowledge.context_selected` events on the current request's session and trace.
Both chat routes flush these events before `model.request_started`. The existing
trace store preserves them for inspection and replay.

The Knowledge retrieval panel lists triggered, enabled KBs searched and the exact
source paths, sections, and chunk IDs packed into model context. The ranked shortlist
count is the bounded retrieval result (currently up to three), not all matching files.
Missing or empty KBs can produce a completed search with zero results; this is not an
integrity or freshness check. Ordinary requests with no KB trigger emit no KB events.

Packing respects the existing knowledge token allocation, keeps each selected source's
citation intact, and marks clipped excerpts. Sources that cannot fit are omitted.
Telemetry contains source metadata, counts, and token estimates, never document content
or the query. The graph connects REFERENCE KNOWLEDGE to MODEL only when at least one
source was included. The panel explicitly labels references as NOT LIVE EVIDENCE;
prepared context is not proof that the model used a source or that a source is current.

Live validation: ask “Using the Open WebUI knowledge base, explain how hybrid search
works in RAG. Cite the source document or section, and label the answer as reference
guidance rather than a live inspection.” Check source paths/chunk IDs in the reference
panel, then inspect/replay the same trace. A new unrelated prompt should reset the panel.
