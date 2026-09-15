import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../src/api/episodic.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText;
const { EMPTY_RECALL, recallForEvent } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("live and replay retain selected historical provenance and reset on next prompt", () => {
  const events = [
    { event_type: "episodic.search_started" },
    { event_type: "episodic.search_completed", metadata: { matched_count: 2 } },
    { event_type: "episodic.context_selected", metadata: {
      matched_count: 2, selected_count: 1, omitted_count: 1, token_budget: 1200, estimated_tokens: 1199,
      episodes: [{ episode_id: "episode", trace_id: "historical-trace", summary_truncated: true }],
    } },
    { event_type: "model.request_completed" },
  ];
  let live = EMPTY_RECALL;
  for (const event of events) live = recallForEvent(live, event);
  assert.deepEqual(events.reduce(recallForEvent, EMPTY_RECALL), live);
  assert.equal(live.selected, 1);
  assert.equal(live.omitted, 1);
  assert.equal(live.episodes[0].traceId, "historical-trace");
  assert.equal(live.episodes[0].shortened, true);
  assert.deepEqual(recallForEvent(live, { event_type: "prompt.received" }), EMPTY_RECALL);
});

test("zero matches differs from no search and malformed rows are ignored", () => {
  const empty = recallForEvent(EMPTY_RECALL, { event_type: "episodic.context_selected", metadata: { matched_count: 0 } });
  assert.equal(empty.phase, "selected");
  assert.equal(empty.selected, 0);
  const malformed = recallForEvent(EMPTY_RECALL, { event_type: "episodic.context_selected", metadata: {
    episodes: [null, {}, { episode_id: "valid", summary_truncated: "false" }], token_budget: -1,
  } });
  assert.equal(malformed.selected, 1);
  assert.equal(malformed.episodes[0].shortened, false);
  assert.equal(malformed.budget, 0);
});
