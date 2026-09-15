import { clearReferenceReceipts } from "./referenceReceipts";
export type Exchange = { prompt: string; response: string };
export type SavedConversation = {
  history: Exchange[];
  prompt: string;
  response: string;
  pending: boolean;
};
const KEY = "cybertron.conversation.v1";

export function restoreConversation(): SavedConversation {
  const empty = { history: [], prompt: "", response: "", pending: false };
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!value || !Array.isArray(value.history) ||
        typeof value.prompt !== "string" || typeof value.response !== "string" ||
        !value.history.every((item: Exchange) => item && typeof item.prompt === "string" && typeof item.response === "string")) return empty;
    return {
      history: value.history.slice(-50), prompt: value.prompt,
      response: value.response + (value.pending ? "\n\n[Connection interrupted by page reload; backend status unknown]" : ""),
      pending: false,
    };
  } catch { return empty; }
}

export function saveConversation(value: SavedConversation): boolean {
  if (!value.prompt && value.history.length === 0) clearReferenceReceipts();
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...value, history: value.history.slice(-50) }));
    return true;
  } catch { return false; }
}
