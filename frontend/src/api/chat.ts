export interface StreamEvent {
  cancel_token?: string;
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
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      message,
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

      onEvent(JSON.parse(trimmed) as StreamEvent);
    }
  }

  if (buffer.trim()) {
    onEvent(JSON.parse(buffer) as StreamEvent);
  }
}
