import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/api/knowledge.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText;
const { EMPTY_KNOWLEDGE, knowledgeForEvent } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("live and replay preserve selected references and reset for the next request", () => {
  const events = [
    { event_type: "knowledge.search_started", metadata: { knowledge_bases: [{ name: "Open WebUI" }] } },
    { event_type: "knowledge.search_completed", metadata: { matched_count: 3 } },
    { event_type: "knowledge.context_selected", metadata: { knowledge_bases: [{ name: "Open WebUI" }],
      matched_count: 3, omitted_count: 2, token_budget: 200, estimated_tokens: 200,
      sources: [{ path: "rag.md", chunk_id: "c1", section: "Hybrid", excerpt_shortened: true }] } },
    { event_type: "model.request_completed" },
  ];
  let live = EMPTY_KNOWLEDGE;
  for (const e of events) live = knowledgeForEvent(live, e);
  assert.deepEqual(live, events.reduce(knowledgeForEvent, EMPTY_KNOWLEDGE));
  assert.equal(live.sources[0].chunk, "c1");
  assert.equal(live.sources[0].shortened, true);
  assert.equal(live.omitted, 2);
  assert.deepEqual(knowledgeForEvent(live, { event_type: "prompt.received" }), EMPTY_KNOWLEDGE);
});
test("empty and malformed metadata never invent sources", () => {
  const state = knowledgeForEvent(EMPTY_KNOWLEDGE, { event_type: "knowledge.context_selected",
    metadata: { sources: [null, {}, { path: 9 }], estimated_tokens: -2 } });
  assert.equal(state.sources.length, 0);
  assert.equal(state.tokens, 0);
});
