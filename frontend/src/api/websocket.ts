export interface CoreEvent {
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export function connectCoreWebSocket(
  onEvent: (event: CoreEvent) => void,
  onStatus: (connected: boolean) => void
): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

  const socket = new WebSocket(
    `${protocol}//${window.location.host}/ws`
  );

  socket.addEventListener("open", () => {
    onStatus(true);
  });

  socket.addEventListener("close", () => {
    onStatus(false);
  });

  socket.addEventListener("error", () => {
    onStatus(false);
  });

  socket.addEventListener("message", (message) => {
    const event = JSON.parse(message.data) as CoreEvent;
    onEvent(event);
  });

  return socket;
}
