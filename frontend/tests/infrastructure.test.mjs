import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/api/infrastructure.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ES2022}}).outputText;
const {filterInfrastructure, getInfrastructure} = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("filters search details and remove dangling edges without changing evidence", () => {
  const snapshot = {nodes: [
    {id:"a",kind:"host",label:"host",state:"observed",details:{}},
    {id:"b",kind:"container",label:"voice",state:"running",details:{image:"kokoro:v1"}},
  ], edges:[{source:"a",target:"b",relation:"TEST"}]};
  assert.equal(filterInfrastructure(snapshot,"","all").edges.length, 1);
  const result = filterInfrastructure(snapshot,"KOKORO","container");
  assert.deepEqual(result.nodes.map(n=>n.id), ["b"]);
  assert.deepEqual(result.edges, []);
  assert.equal(snapshot.nodes.length, 2);
  assert.equal(filterInfrastructure(snapshot,"missing","all").nodes.length, 0);
});

test("failed refresh rejects instead of turning failure into an empty snapshot", async () => {
  const prior = globalThis.fetch;
  globalThis.fetch = async () => ({ok:false,status:503});
  try { await assert.rejects(getInfrastructure(new AbortController().signal), /503/); }
  finally { globalThis.fetch = prior; }
});
