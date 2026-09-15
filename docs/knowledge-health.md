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
