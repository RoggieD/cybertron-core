import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { filterInfrastructure, getInfrastructure, type InfrastructureSnapshot } from "../api/infrastructure";
import "../infrastructure.css";

const Scene = lazy(() => import("./InfrastructureScene"));

export default function InfrastructureExplorer() {
  const [snapshot, setSnapshot] = useState<InfrastructureSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const request = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError("");
    try {
      const result = await getInfrastructure(controller.signal);
      if (!controller.signal.aborted) { setSnapshot(result); setClock(Date.now()); }
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Unable to collect infrastructure");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }, []);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => setClock(Date.now()), 10000);
    return () => { request.current?.abort(); window.clearInterval(timer); }; }, [refresh]);
  const graph = useMemo(() => snapshot ? filterInfrastructure(snapshot, query, kind) : {nodes: [], edges: []}, [snapshot, query, kind]);
  const detail = graph.nodes.find(node => node.id === selected);
  const stale = !!snapshot && clock - Date.parse(snapshot.finished_at) > 60000;
  return <section className="infrastructure-panel" aria-label="Infrastructure explorer">
    <header><div><p className="eyebrow">OBSERVED INFRASTRUCTURE</p><h2>Infrastructure explorer</h2></div>
      <button type="button" disabled={busy} onClick={() => void refresh()}>{busy ? "INSPECTING…" : "REFRESH SNAPSHOT"}</button></header>
    <p>Host, Docker endpoint, containers and service targets. These are timestamped observations, not continuous live state.</p>
    {error && <p role="alert">{error}. {snapshot ? "Previous snapshot retained; it may be out of date." : "No snapshot available."}</p>}
    {snapshot && <>
      <p className="infrastructure-stamp">{stale || error ? "OLDER SNAPSHOT — REFRESH TO RECHECK" : "RECENT SNAPSHOT"} · {new Date(snapshot.finished_at).toLocaleString()} · {snapshot.nodes.length} entities
        {snapshot.omitted > 0 && ` · ${snapshot.omitted} omitted by size limit`}</p>
      {snapshot.sources.filter(source => source.error).map(source => <p role="alert" key={source.tool}>{source.tool}: {source.error}</p>)}
      <div className="infrastructure-toolbar">
        <label>Search <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Name, state, image or target" /></label>
        <label>Type <select value={kind} onChange={event => setKind(event.target.value)}>{["all", "host", "engine", "container", "service"].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        <button type="button" onClick={() => {setSelected(null); setView(current => current + 1);}}>RESET VIEW</button>
      </div>
      <p className="infrastructure-help">Drag to rotate · Scroll to zoom · Select a node or entity to inspect and focus. Cyan: host · Purple: Docker · Green: containers · Amber: services · Red: failed check or exited container.</p>
      <Suspense fallback={<p>Loading 3D view…</p>}><Scene key={view} {...graph} selected={detail?.id ?? null} onSelect={setSelected} /></Suspense>
      <div className="infrastructure-inspection">
        <div className="infrastructure-entities" aria-label="Infrastructure entities">
          <p>{graph.nodes.length} matching entities</p>
          {graph.nodes.map(node => <button type="button" key={node.id} aria-pressed={node.id === detail?.id} onClick={() => setSelected(node.id)}>
            <span>{node.kind.toUpperCase()}</span><strong>{node.label}</strong><small>{node.state}</small>
          </button>)}
          {!graph.nodes.length && <p>No entities match this view.</p>}
        </div>
        <aside aria-label="Entity details" aria-live="polite">
          {detail ? <><h3>{detail.label}</h3><p>{detail.kind} · {detail.state}</p>
            <p>Source: <code>{detail.source}</code><br />Observed: {new Date(detail.observed_at).toLocaleString()}</p>
            <dl>{Object.entries(detail.details).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value == null ? "Not reported" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}</dd></div>)}</dl>
            <h4>Relationships</h4>
            {snapshot.edges.filter(edge => edge.source === detail.id || edge.target === detail.id).map(edge => <p key={`${edge.source}:${edge.target}`}>
              {snapshot.nodes.find(n => n.id === edge.source)?.label} → <strong>{edge.relation}</strong> → {snapshot.nodes.find(n => n.id === edge.target)?.label}<br /><small>{edge.basis}</small>
            </p>)}
          </> : <p>Select an entity to inspect its recorded state and relationships.</p>}
          <p>Snapshot trace: <a href={`/api/traces/${encodeURIComponent(snapshot.trace_id)}`} target="_blank" rel="noreferrer">{snapshot.trace_id}</a></p>
          <small>Saved trace records are historical evidence of this inspection. Service reachability does not establish application health or deployment location.</small>
        </aside>
      </div>
    </>}
  </section>;
}
