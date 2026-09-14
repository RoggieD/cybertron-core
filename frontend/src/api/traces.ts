import type { CoreEvent } from "./websocket";

export type TraceSummary = {
  trace_id: string;
  started_at: string;
  ended_at: string;
  event_count: number;
  completed: number | boolean;
  errored: number | boolean;
};

export type TraceDetail = {
  trace_id: string;
  count: number;
  started_at: string;
  ended_at: string;
  completed: boolean;
  errored: boolean;
  events: CoreEvent[];
};

export async function getTraceSummaries(limit = 12): Promise<TraceSummary[]> {
  const response = await fetch(`/api/traces/summaries?limit=${limit}`);
  if (!response.ok) {
    throw new Error(`Unable to load trace summaries (${response.status})`);
  }

  const payload = (await response.json()) as { traces?: TraceSummary[] };
  return payload.traces ?? [];
}

export async function getTraceDetail(traceId: string): Promise<TraceDetail> {
  const response = await fetch(`/api/traces/${encodeURIComponent(traceId)}`);
  if (!response.ok) {
    throw new Error(`Unable to load trace ${traceId} (${response.status})`);
  }

  return (await response.json()) as TraceDetail;
}
