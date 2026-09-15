type Exchange = { prompt: string; response: string };
type Receipt = Exchange & { token: string };
const KEY = "cybertron.reference-receipts.v1";

function receipts(): Receipt[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(value) ? value.filter((r) => r && typeof r.prompt === "string" &&
      typeof r.response === "string" && typeof r.token === "string").slice(-12) : [];
  } catch { return []; }
}

export function clearReferenceReceipts(): void {
  try { localStorage.removeItem(KEY); } catch { /* Missing storage means no continuity. */ }
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
  try { localStorage.setItem(KEY, JSON.stringify((token ? [...prior, { prompt, response, token }] : prior).slice(-12))); }
  catch { /* The next request will accurately report unavailable provenance. */ }
}
