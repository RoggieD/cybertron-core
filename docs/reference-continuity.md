# Reference citation follow-ups

Each model request that packs reference sources retains their exact metadata in
`reference_receipts` in `data/cybertron.db`. The completed response returns an opaque
`reference_receipt` token. Tokens are not broadcast in event telemetry. Stored metadata
contains KB identity, source path, section, chunk ID, excerpt-shortening flag, and the
original request trace; it does not duplicate document content or model output.

The browser retains up to 12 receipts in memory, matching each to its completed
prompt/answer. The active chat passes its conversation snapshot directly to the request
transport, which sends the receipt for the immediately preceding exchange. Live continuity
does not depend on delayed conversation saves or successful localStorage writes.
Storage is a best-effort reload backup: if it is unavailable, live follow-ups still work,
but continuity cannot survive a page reload. NEW CHAT clears both the in-memory receipts
and their stored backup when possible. Incomplete or altered answers do not match a receipt.
API clients can pass the completed response's `reference_receipt` in a subsequent chat
request. Treat the opaque token as access to that answer's source metadata.

An explicit citation follow-up such as "Cite the source paths and chunk IDs supporting
your previous answer" retrieves the retained metadata instead of running a new KB search
or implicit live tool. Ordinary conversation does not inject those references. Unknown
or absent receipts produce an explicit unavailable-provenance instruction, never a claim
that the earlier answer had no retrieval. Browser-supplied citation text is not trusted
as the retained source record.

Citation metadata is packed within the existing knowledge context budget and labeled
reference knowledge. It records what was prepared for the prior answer, not which
sources the model actually relied on or whether every claim was supported. It does not
establish current source freshness or live system state. Receipts continue to identify
the original chunks after a KB refresh; the follow-up does not substitute newly ranked
chunks or fetch old document contents.

Processing Graph telemetry marks this path with `provenance_reused`. The panel shows
"Prior citation lookup", "Retained citation metadata", and the original request trace.
The existing trace replay preserves these distinctions.

## Live validation

Rebuild the frontend, refresh the browser, and start NEW CHAT. Ask:

> Using the Open WebUI knowledge base, explain how hybrid search works in RAG. Cite the source document and chunk ID, and label the answer as reference guidance.

Then, in the same conversation:

> Cite the source paths and chunk IDs supporting your previous answer. Do not invent citations.

The follow-up should cite the same selected source records without invoking a service
inspection. An answer generated before this update has no receipt; start a fresh exchange
instead of expecting its provenance to be reconstructed from conversation text.
