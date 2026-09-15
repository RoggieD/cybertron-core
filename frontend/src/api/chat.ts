import { previousReferenceReceipt, rememberReferenceReceipt } from "./referenceReceipts";
export interface StreamEvent {
  cancel_token?: string;
  reference_receipt?: string | null;
  event: string;
  model?: string;
  content?: string;
  done?: boolean;
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  eval_count?: number;
  error?: string;
  tool?: string;
  verified?: boolean;
}

export type ConversationExchange = {
  prompt: string;
  response: string;
};

const CONVERSATION_KEY = "cybertron.conversation.v1";
const MODEL_HISTORY_LIMIT = 12;

function browserConversationHistory(): ConversationExchange[] {
  try {
    const saved = JSON.parse(localStorage.getItem(CONVERSATION_KEY) || "null");
    if (!saved) return [];

    const history = Array.isArray(saved.history)
      ? saved.history.filter(
          (item: ConversationExchange) =>
            item && typeof item.prompt === "string" && typeof item.response === "string",
        )
      : [];

    if (
      typeof saved.prompt === "string" && saved.prompt.trim() &&
      typeof saved.response === "string" && saved.response.trim()
    ) {
      history.push({ prompt: saved.prompt, response: saved.response });
    }

    return history.slice(-MODEL_HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export async function cancelChat(token: string): Promise<string> {
  const response = await fetch("/api/chat/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) throw new Error(`Cancellation not acknowledged (${response.status}). Retry CANCEL.`);
  return (await response.json()).status;
}

export async function streamChat(
  message: string,
  onEvent: (event: StreamEvent) => void,
  agentId?: string | null,
  signal?: AbortSignal,
): Promise<void> {
  const history = browserConversationHistory();
  let answer = "";
  const deliver = (event: StreamEvent) => {
    if (event.event === "tool.result" && event.content) rememberReferenceReceipt(message, event.content, null);
    if (event.event === "model.token") answer += event.content ?? "";
    if (event.event === "model.request_completed" && event.done) {
      rememberReferenceReceipt(message, answer, event.reference_receipt);
    }
    onEvent(event);
  };
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message,
      history,
      reference_receipt: previousReferenceReceipt(history),
      agent_id: agentId && agentId !== "auto" ? agentId : null,
    })
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Streaming response body unavailable");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();

      if (!trimmed) {
        continue;
      }

      deliver(JSON.parse(trimmed) as StreamEvent);
    }
  }

  if (buffer.trim()) {
    deliver(JSON.parse(buffer) as StreamEvent);
  }
}
