import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const source = readFileSync(new URL("../src/api/referenceReceipts.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText;
const { previousReferenceReceipt, rememberReferenceReceipt } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("receipts bind to the last answer, survive reload, and reset on NEW CHAT", () => {
  const values = new Map();
  globalThis.localStorage = { getItem: k => values.get(k), setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) };
  const first = { prompt: "Explain RAG", response: "Reference guidance" };
  rememberReferenceReceipt(first.prompt, first.response, "receipt");
  assert.equal(previousReferenceReceipt([first]), "receipt");
  assert.equal(previousReferenceReceipt([first, { prompt: "Hello", response: "Hi" }]), null);
  assert.equal(previousReferenceReceipt([{ ...first, response: "Altered answer" }]), null);
  assert.equal(previousReferenceReceipt([]), null);
  assert.equal(previousReferenceReceipt([first]), null);
});
test("unavailable browser storage yields no receipt", () => {
  globalThis.localStorage = { getItem() { throw Error("unavailable"); }, setItem() { throw Error("unavailable"); } };
  rememberReferenceReceipt("prompt", "response", "receipt");
  assert.equal(previousReferenceReceipt([{ prompt: "prompt", response: "response" }]), null);
});

test("stream transport returns the receipt only with its matching completed answer", async () => {
  const values = new Map();
  globalThis.localStorage = { getItem: k => values.get(k), setItem: (k,v) => values.set(k,v), removeItem: k => values.delete(k) };
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`;
  const chatSource = readFileSync(new URL("../src/api/chat.ts", import.meta.url), "utf8");
  const chatCode = ts.transpileModule(chatSource, { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
    .replace('"./referenceReceipts"', JSON.stringify(moduleUrl));
  const { streamChat } = await import(`data:text/javascript;base64,${Buffer.from(chatCode).toString("base64")}`);
  const requests = [];
  globalThis.fetch = async (_, options) => {
    requests.push(JSON.parse(options.body));
    return new Response([
      { event: "model.token", content: "Reference answer" },
      { event: "model.request_completed", done: true, reference_receipt: "opaque-token" },
    ].map(JSON.stringify).join("\n"));
  };
  await streamChat("Explain hybrid search", () => {});
  assert.equal(requests[0].reference_receipt, null);
  values.set("cybertron.conversation.v1", JSON.stringify({ history: [], prompt: "Explain hybrid search", response: "Reference answer" }));
  await streamChat("Cite your previous answer", () => {});
  assert.equal(requests[1].reference_receipt, "opaque-token");
  rememberReferenceReceipt("Explain hybrid search", "Reference answer", null);
  assert.equal(previousReferenceReceipt([{ prompt: "Explain hybrid search", response: "Reference answer" }]), null);
});
