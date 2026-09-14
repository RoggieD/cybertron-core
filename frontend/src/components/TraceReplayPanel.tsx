import { useEffect, useState } from "react";

import {
  getTraceDetail,
  getTraceSummaries,
  type TraceDetail,
  type TraceSummary,
} from "../api/traces";

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function durationMs(trace: TraceSummary): number {
  const start = new Date(trace.started_at).getTime();
  const end = new Date(trace.ended_at).getTime();
  return Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : 0;
}

export default function TraceReplayPanel({
  onLoad,
  onReplay,
  replaying,
}: {
  onLoad: (trace: TraceDetail) => void;
  onReplay: (trace: TraceDetail) => void;
  replaying: boolean;
}) {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setTraces(await getTraceSummaries(12));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load traces");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function openTrace(traceId: string, replay: boolean) {
    setSelectedTrace(traceId);
    setError(null);
    try {
      const trace = await getTraceDetail(traceId);
      if (replay) onReplay(trace);
      else onLoad(trace);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load trace");
    }
  }

  return (
    <section className="trace-replay-panel" aria-label="Historical trace replay">
      <div className="trace-replay-header">
        <div>
          <span>TRACE HISTORY / FORENSICS</span>
          <strong>Replay prior C.O.R.E. reasoning and evidence flows</strong>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading || replaying}>
          {loading ? "LOADING…" : "REFRESH"}
        </button>
      </div>

      {error && <div className="trace-replay-error">{error}</div>}

      <div className="trace-replay-list">
        {traces.length === 0 && !loading ? (
          <div className="trace-replay-empty">No persisted traces available yet.</div>
        ) : (
          traces.map((trace) => {
            const completed = Boolean(trace.completed);
            const errored = Boolean(trace.errored);
            return (
              <article
                key={trace.trace_id}
                className={selectedTrace === trace.trace_id ? "selected" : ""}
              >
                <div className="trace-replay-id">
                  <span>TRACE</span>
                  <strong title={trace.trace_id}>{trace.trace_id.slice(0, 12)}</strong>
                </div>
                <div>
                  <span>STARTED</span>
                  <strong>{formatTime(trace.started_at)}</strong>
                </div>
                <div>
                  <span>EVENTS</span>
                  <strong>{trace.event_count}</strong>
                </div>
                <div>
                  <span>DURATION</span>
                  <strong>{(durationMs(trace) / 1000).toFixed(1)}s</strong>
                </div>
                <div>
                  <span>RESULT</span>
                  <strong className={errored ? "error" : completed ? "complete" : "incomplete"}>
                    {errored ? "ERROR" : completed ? "COMPLETE" : "INCOMPLETE"}
                  </strong>
                </div>
                <div className="trace-replay-actions">
                  <button
                    type="button"
                    disabled={replaying}
                    onClick={() => void openTrace(trace.trace_id, false)}
                  >
                    INSPECT
                  </button>
                  <button
                    type="button"
                    disabled={replaying}
                    onClick={() => void openTrace(trace.trace_id, true)}
                  >
                    REPLAY
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}
