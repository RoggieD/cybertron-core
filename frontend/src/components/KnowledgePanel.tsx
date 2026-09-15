import type { KnowledgeState } from "../api/knowledge";

export default function KnowledgePanel({ knowledge: k }: { knowledge: KnowledgeState }) {
  return <section className="episodic-recall-panel reference-knowledge-panel" aria-label="Reference knowledge retrieval">
    <header><div><span>REFERENCE KNOWLEDGE</span><h2>Knowledge retrieval</h2></div>
      <strong>REFERENCE · NOT LIVE EVIDENCE</strong></header>
    {k.phase === "not_queried" ? <p>No knowledge-base search recorded for this request.</p> : <>
      <p>{k.reused ? "Prior reference knowledge bases" : "Knowledge bases searched"}: {k.bases.join(", ") || "Not recorded"}</p>
      <ol className="episodic-recall-flow" aria-label="Reference retrieval progress">
        <li>{k.reused ? "Prior citation lookup" : "Search"} <strong>{k.phase === "searching" ? "Searching…" : "Complete"}</strong></li>
        <li>{k.reused ? "Retained sources" : "Ranked shortlist"} <strong>{k.phase === "searching" ? "—" : k.matched}</strong></li>
        <li>Selected sources <strong>{k.phase === "selected" ? k.sources.length : "—"}</strong></li>
        <li>Model context <strong>{k.phase !== "selected" ? "Waiting" : k.sources.length ? "Prepared" : "No references added"}</strong></li>
      </ol>
      {k.phase === "selected" && <p>{k.tokens} / {k.budget} estimated tokens · {k.omitted} omitted from context.
        {k.matched === 0 && " No relevant references found."}</p>}
      <div className="episodic-recall-records">{k.sources.map((s, i) => <article key={`${s.kb}:${s.path}:${s.chunk}:${i}`}>
        <div><strong>{s.section || s.path}</strong><span>{k.reused ? "Retained citation metadata" : s.shortened ? "Shortened excerpt" : "Full retrieved excerpt"}</span></div>
        <dl><dt>Knowledge base</dt><dd>{s.name || s.kb || "Not recorded"}</dd>
          <dt>Source document</dt><dd>{s.path}</dd><dt>Chunk ID</dt><dd>{s.chunk || "Not applicable (document)"}</dd>{s.originTrace && <><dt>Original request trace</dt><dd>{s.originTrace}</dd></>}</dl>
      </article>)}</div>
    </>}
    <small>Sources prepared for the model, not proof of its reasoning, source freshness, or current system state. Document contents are not copied into telemetry.</small>
  </section>;
}
