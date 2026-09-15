import type { CoreEvent } from "./websocket";

export type RecallEpisode = {
  episodeId: string;
  traceId: string | null;
  timestamp: string | null;
  toolId: string | null;
  shortened: boolean;
};

export type RecallState = {
  phase: "not_queried" | "searching" | "matched" | "selected";
  matched: number;
  selected: number;
  omitted: number;
  budget: number;
  tokens: number;
  episodes: RecallEpisode[];
};

export const EMPTY_RECALL: RecallState = {
  phase: "not_queried", matched: 0, selected: 0, omitted: 0,
  budget: 0, tokens: 0, episodes: [],
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
}

export function recallForEvent(current: RecallState, event: CoreEvent): RecallState {
  if (event.event_type === "prompt.received") return EMPTY_RECALL;
  if (event.event_type === "episodic.search_started") return { ...EMPTY_RECALL, phase: "searching" };
  const metadata = event.metadata ?? {};
  if (event.event_type === "episodic.search_completed") {
    return { ...current, phase: "matched", matched: count(metadata.matched_count) };
  }
  if (event.event_type !== "episodic.context_selected") return current;
  const episodes: RecallEpisode[] = [];
  for (const value of Array.isArray(metadata.episodes) ? metadata.episodes.slice(0, 25) : []) {
    if (!value || typeof value !== "object") continue;
    const row = value as Record<string, unknown>;
    const episodeId = text(row.episode_id);
    if (!episodeId) continue;
    episodes.push({ episodeId, traceId: text(row.trace_id), timestamp: text(row.timestamp),
      toolId: text(row.tool_id), shortened: row.summary_truncated === true });
  }
  return { phase: "selected", matched: count(metadata.matched_count),
    selected: episodes.length, omitted: count(metadata.omitted_count),
    budget: count(metadata.token_budget), tokens: count(metadata.estimated_tokens), episodes };
}
