import type { CoreEvent } from "./websocket";

type Source = { kb: string; name: string; path: string; section: string; chunk: string; shortened: boolean };
export type KnowledgeState = {
  phase: "not_queried" | "searching" | "matched" | "selected";
  bases: string[]; matched: number; omitted: number; budget: number; tokens: number; sources: Source[];
};
export const EMPTY_KNOWLEDGE: KnowledgeState = {
  phase: "not_queried", bases: [], matched: 0, omitted: 0, budget: 0, tokens: 0, sources: [],
};
const text = (v: unknown): string => typeof v === "string" ? v : "";
const count = (v: unknown): number => typeof v === "number" && Number.isFinite(v) ? Math.max(0, Math.floor(v)) : 0;
const rows = (v: unknown): Record<string, unknown>[] => Array.isArray(v)
  ? v.slice(0, 25).filter((r) => r && typeof r === "object") : [];

export function knowledgeForEvent(current: KnowledgeState, event: CoreEvent): KnowledgeState {
  if (event.event_type === "prompt.received") return EMPTY_KNOWLEDGE;
  const m = event.metadata ?? {};
  const bases = rows(m.knowledge_bases).map((r) => text(r.name) || text(r.id)).filter(Boolean);
  if (event.event_type === "knowledge.search_started") return { ...EMPTY_KNOWLEDGE, phase: "searching", bases };
  if (event.event_type === "knowledge.search_completed") return { ...current, phase: "matched", matched: count(m.matched_count) };
  if (event.event_type !== "knowledge.context_selected") return current;
  return { phase: "selected", bases, matched: count(m.matched_count), omitted: count(m.omitted_count),
    budget: count(m.token_budget), tokens: count(m.estimated_tokens),
    sources: rows(m.sources).filter((r) => text(r.path)).map((r) => ({
      kb: text(r.kb), name: text(r.name), path: text(r.path), section: text(r.section),
      chunk: text(r.chunk_id), shortened: r.excerpt_shortened === true,
    })),
  };
}
