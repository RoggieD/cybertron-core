# Historical operational recall

Recall uses the existing SQLite episode store and event projections. Prompts
containing recall cues (before, previously, last time, history, recall, recurrence)
retrieve up to five episodes. Ordinary conversation does not search episodes.
Subjectless follow-ups use only the latest browser-provided user prompt; without
a subject, no history is injected. Assistant responses are not search evidence.

At least half the meaningful query terms must match an episode's prompt, outcome,
tool, agent, or tags. Lexical coverage ranks first, followed by the existing
salience formula (recency, importance, pain, capped recurrence), timestamp and ID.
Old episodes remain eligible even when their recency score is zero. The scan
covers all episodes, retaining only the best candidates in memory; search cost
is linear in stored history. This is lexical retrieval, not semantic search.

The dedicated episodic slice uses 5% of the prompt budget, taken from persistent
memory (now 10%). Instructions, tool evidence, conversation and knowledge retain
their allocations. Complete JSON records are packed under the existing token
estimate; oversized records are omitted, preserving the warning and provenance.
Records include episode, current/previous trace and source-event IDs where stored.
The current request's trace is excluded. Consolidation preserves only the prior
trace available in the existing schema, not a complete recurrence trace list.

`format_memory_context` supplies the explicitly labeled historical section to
`build_messages`. Historical summaries are data, never instructions or current
observations. Recorded outcomes do not independently establish that a fix worked.
Current-request tools retain authority. Historical recall bypasses implicit live
tool selection, including the broad "what happened" incident shortcut, and
reaches model context. Explicit persistent-memory search keeps its existing tool.
Trailing citation/evidence-format instructions are excluded from subject matching.
Request a current inspection separately when a fresh observation is needed.

## Live validation

After pulling main on GM-AI01, ask in the C.O.R.E. browser:

> What happened last time we inspected Docker? Cite the historical episode and
> trace IDs, and distinguish that history from any current tool result.

With matching recorded episodes, expect historical summaries with provenance.
Without matches, expect no invented history. After a specific operational question,
also try “Have we seen this before?” to exercise subject resolution.
