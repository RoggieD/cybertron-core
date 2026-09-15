# Controlled knowledge refresh

C.O.R.E. can check, build, validate, and activate a replacement reference KB.
This adapts the Markdown/MDX section splitting, chunk IDs, provenance hashes,
source configuration, and rollback workflow from CyberTron Agentic Stack's
`.agent/tools/kb_chunk.py` and `.agent/tools/kb_manage.py`.

## Operator workflow

Run from the C.O.R.E. repository with its virtual environment:

```bash
.venv/bin/python -m backend.app.knowledge.refresh check open-webui
.venv/bin/python -m backend.app.knowledge.refresh apply open-webui
.venv/bin/python -m backend.app.knowledge.health verify open-webui
```

`check` downloads the configured Git source and builds a validated candidate,
but does not activate it. `apply` acquires and validates the source again, then
activates that snapshot. A source can change between these two commands; the
apply result reports the actual checked-out commit. Neither command establishes
that documentation is authoritative or that any live service matches it.

Open WebUI uses `https://github.com/open-webui/docs.git`, branch `main`, directory
`docs`, with Agentic Stack's extensions and excluded presentation pages. Git must
be installed; acquisition has a timeout and disables interactive authentication.
There is no background scheduler, implicit chat refresh, or mutating HTTP endpoint.

For an existing local source directory, including the Agentic Stack checkout:

```bash
.venv/bin/python -m backend.app.knowledge.refresh check open-webui --source /srv/cybertron-data/agentic-stack-lab/cybertron/.agent/knowledge/open-webui/source/docs
.venv/bin/python -m backend.app.knowledge.refresh apply open-webui --source /srv/cybertron-data/agentic-stack-lab/cybertron/.agent/knowledge/open-webui/source/docs
```

Local input must contain original documents, not generated chunk JSON. Local
imports do not assert an upstream commit or remote freshness. Other enabled chunk
KBs can use `--source`; document-only KBs such as Ollama are not converted.

## Activation and rollback

Each candidate lives under `data/knowledge-runtime/<kb>/versions/<generation>/`,
outside the tracked reference files. Its copied source bytes and generated chunks
have manifest hashes. Before activation, verification requires nonempty documents,
usable chunks for every included document, matching KB identity, unique chunk IDs,
complete source provenance, and valid hashes. Empty input, invalid UTF-8, symlinks,
download errors, or validation failures leave the active pointer unchanged.

The only operation that changes retrieval is an atomic replacement of `active.json`.
Retrieval resolves that pointer once per KB search and keeps using the same directory
for the search. Prior versions are retained, so a concurrent reader can finish after
activation. Original registered chunks remain untouched and serve until the first
successful activation. No backend restart is needed to read a newly activated version.

```bash
.venv/bin/python -m backend.app.knowledge.refresh rollback open-webui
```

Rollback validates the previous version before switching. The first rollback returns
to the original registered chunks, provided they still pass validation. Later rollbacks
switch between the two most recently selected versions. A malformed prior snapshot is
rejected rather than activated.

One writer per KB is allowed. A process crash can leave `refresh.lock`; after confirming
that no refresh process remains, an operator may remove that specific lock file and retry.
Readers do not require this lock. Atomic activation avoids partial updates during process
failures; it is not a guarantee against filesystem corruption or power loss.

Candidates, failed attempts, and Git checkouts are retained for diagnosis. Repeated checks
consume disk space; automatic retention cleanup is not included. Never remove an active
or previous generation, or one still being read by a running request.

## Status and validation

The health CLI and read-only `GET /api/knowledge/status` report local reference health
plus a separate `refresh` section: active generation, previous generation, active source
provenance, and last refresh attempt. They do not contact upstream. A last failed attempt
does not mean that the active KB failed; consult its separate integrity status.

Added/changed/removed document counts compare source byte hashes to the active managed
manifest. On first import `baseline_known` is false: existing chunks have no source-byte
baseline, so all candidate documents are reported as added. Identical input and generated
chunks report `unchanged`, without switching the active version.

After activation, repeat the Open WebUI hybrid-search question. The answer and Processing
Graph should cite the selected document/section and chunk ID as reference knowledge, never
live system evidence. Chunk IDs can change when the documentation content changes.
