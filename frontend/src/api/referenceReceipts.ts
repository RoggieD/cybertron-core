type Exchange = { prompt: string; response: string };
type Receipt = Exchange & { token: string };
const KEY = "cybertron.reference-receipts.v1";
let activeReceipts: Receipt[] | undefined;

function receipts(): Receipt[] {
  if (activeReceipts !== undefined) return [...activeReceipts];
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || "[]");
    activeReceipts = Array.isArray(value) ? value.filter((r) => r && typeof r.prompt === "string" &&
      typeof r.response === "string" && typeof r.token === "string").slice(-12) : [];
  } catch { activeReceipts = []; }
  return [...activeReceipts];
}

export function clearReferenceReceipts(): void {
  activeReceipts = [];
  try { localStorage.removeItem(KEY); } catch { /* Active chat is cleared even without storage. */ }
}

export function previousReferenceReceipt(history: Exchange[]): string | null {
  const previous = history.at(-1);
  if (!previous) { clearReferenceReceipts(); return null; }
  // Match the immediately preceding complete exchange, never an unrelated older answer.
  return receipts().reverse().find((r) => r.prompt.trim() === previous.prompt.trim() &&
    r.response.trim() === previous.response.trim())?.token ?? null;
}

export function rememberReferenceReceipt(prompt: string, response: string, token?: string | null): void {
  if (!response.trim()) return;
  const prior = receipts().filter((r) => r.prompt.trim() !== prompt.trim() || r.response.trim() !== response.trim());
  activeReceipts = (token ? [...prior, { prompt, response, token }] : prior).slice(-12);
  try { localStorage.setItem(KEY, JSON.stringify(activeReceipts)); }
  catch { /* Continue in memory; reload persistence is unavailable. */ }
}
