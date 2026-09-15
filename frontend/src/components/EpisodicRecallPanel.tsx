import type { RecallState } from "../api/episodic";

export default function EpisodicRecallPanel({ recall }: { recall: RecallState }) {
  return (
    <section className="episodic-recall-panel" aria-label="Historical operational recall">
      <header><div><span>HISTORICAL OPERATIONAL MEMORY</span><h2>Episodic recall</h2></div>
        <strong>HISTORY · NOT LIVE EVIDENCE</strong></header>
      {recall.phase === "not_queried" ? <p>No episodic search recorded for this request.</p> : <>
        <ol className="episodic-recall-flow" aria-label="Recall progress">
          <li>Search <strong>{recall.phase === "searching" ? "Searching…" : "Complete"}</strong></li>
          <li>Matches <strong>{recall.phase === "searching" ? "—" : recall.matched}</strong></li>
          <li>Selected history <strong>{recall.phase === "selected" ? recall.selected : "—"}</strong></li>
          <li>Model context <strong>{recall.phase !== "selected" ? "Waiting" : recall.selected ? "Prepared" : "No history added"}</strong></li>
        </ol>
        {recall.phase === "selected" && <p>
          {recall.tokens} / {recall.budget} estimated tokens · {recall.omitted} omitted for budget.
          {recall.matched === 0 && " No relevant episodes found."}
        </p>}
        <div className="episodic-recall-records">
          {recall.episodes.map((episode) => <article key={episode.episodeId}>
            <div><strong>{episode.toolId ?? "Operational episode"}</strong>
              <span>{episode.shortened ? "Shortened to fit budget" : "Full stored summary"}</span></div>
            <dl><dt>Episode ID</dt><dd>{episode.episodeId}</dd>
              <dt>Historical trace ID</dt><dd>{episode.traceId ?? "Not recorded"}</dd>
              <dt>Recorded</dt><dd>{episode.timestamp ?? "Not recorded"}</dd></dl>
          </article>)}
        </div>
      </>}
      <small>These are records prepared for the model, not proof of its reasoning or current system state. Episode contents are not copied into telemetry.</small>
    </section>
  );
}
