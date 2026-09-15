import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

const source = readFileSync(new URL("../src/api/voice.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022 },
}).outputText;
const { synthesizeSpeech } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("speech summaries preserve facts and fall back for security narratives", async () => {
  const originalFetch = globalThis.fetch;
  let spoken;
  globalThis.fetch = async (_url, options) => {
    spoken = JSON.parse(options.body).text;
    return { ok: true, blob: async () => new Blob() };
  };
  try {
    await synthesizeSpeech("SECURITY STATUS — VERIFIED\nApproved: 16 Drift: 0 Learned: 2");
    assert.match(spoken, /16 endpoints are approved/);
    assert.match(spoken, /0 policy drift/);
    assert.match(spoken, /2 learned-only/);
    await synthesizeSpeech("Verified Security Findings\nThere are 16 listeners.\n**Summary**: The host matches its approved listener policy. Owner visibility is incomplete.");
    assert.match(spoken, /host matches its approved listener policy/);
    assert.match(spoken, /Owner visibility is incomplete/);
    assert.match(spoken, /not proof that the host is secure/);
    await synthesizeSpeech("Verified security findings. Ownership is unavailable for 24 listeners.");
    assert.match(spoken, /24 listeners/);
    await synthesizeSpeech("SECURITY VERIFIED " + "A long observation without punctuation ".repeat(100));
    assert.ok(spoken.length < 800);
    await synthesizeSpeech("SYSTEM STATUS — VERIFIED\nHostname: gm-ai01\nCPU usage: 2.0%\nMemory usage: 41.1%\nUptime: 0d 21h 52m");
    assert.match(spoken, /21 hours, and 52 minutes/);
    await synthesizeSpeech("Ready.");
    assert.equal(spoken, "Ready.");
  } finally { globalThis.fetch = originalFetch; }
});
