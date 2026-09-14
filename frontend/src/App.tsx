import { FormEvent, useEffect, useState } from "react";

import { getHealth } from "./api/core";
import { streamChat, type StreamEvent } from "./api/chat";
import {
  connectCoreWebSocket,
  type CoreEvent
} from "./api/websocket";

import "./styles.css";

type ReactorState =
  | "IDLE"
  | "THINKING"
  | "COMPLETE"
  | "ERROR";

export default function App() {
  const [apiStatus, setApiStatus] = useState("CHECKING");
  const [socketConnected, setSocketConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<CoreEvent | null>(null);

  const [prompt, setPrompt] = useState("");
  const [responseText, setResponseText] = useState("");
  const [reactorState, setReactorState] =
    useState<ReactorState>("IDLE");

  const [activeModel, setActiveModel] = useState("UNKNOWN");
  const [evalCount, setEvalCount] = useState<number | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);

  useEffect(() => {
    void getHealth()
      .then(() => setApiStatus("ONLINE"))
      .catch(() => setApiStatus("OFFLINE"));

    const socket = connectCoreWebSocket(
      (event) => setLastEvent(event),
      (connected) => setSocketConnected(connected)
    );

    return () => {
      socket.close();
    };
  }, []);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const message = prompt.trim();

    if (!message) {
      return;
    }

    setResponseText("");
    setEvalCount(null);
    setDurationMs(null);
    setReactorState("THINKING");

    try {
      await streamChat(
        message,
        (streamEvent: StreamEvent) => {
          if (streamEvent.model) {
            setActiveModel(streamEvent.model);
          }

          if (
            streamEvent.event === "model.token" &&
            streamEvent.content
          ) {
            setResponseText(
              (current) => current + streamEvent.content
            );
          }

          if (
            streamEvent.event === "model.request_completed"
          ) {
            if (
              typeof streamEvent.eval_count === "number"
            ) {
              setEvalCount(streamEvent.eval_count);
            }

            if (
              typeof streamEvent.total_duration === "number"
            ) {
              setDurationMs(
                streamEvent.total_duration / 1_000_000
              );
            }

            setReactorState("COMPLETE");

            window.setTimeout(() => {
              setReactorState("IDLE");
            }, 1800);
          }

          if (streamEvent.event === "model.error") {
            setReactorState("ERROR");

            setResponseText(
              streamEvent.error ??
                "Unknown model streaming error."
            );
          }
        }
      );
    } catch (error) {
      setReactorState("ERROR");

      setResponseText(
        error instanceof Error
          ? error.message
          : "Unknown request failure."
      );
    }
  }

  return (
    <main className="core-shell">
      <section className="header">
        <p className="eyebrow">CYBERTRON SYSTEMS</p>

        <h1>
          CyberTron <span>C.O.R.E.</span>
        </h1>

        <p className="subtitle">
          CyberTron Orchestration &amp; Reasoning Engine
        </p>
      </section>

      <section
        className={`reactor-panel reactor-${reactorState.toLowerCase()}`}
      >
        <div className="reactor">
          <div className="reactor-core" />
          <div className="reactor-ring ring-one" />
          <div className="reactor-ring ring-two" />
          <div className="reactor-ring ring-three" />
        </div>

        <div className="state-label">
          {reactorState}
        </div>
      </section>

      <section className="conversation-panel">
        <form
          className="prompt-form"
          onSubmit={handleSubmit}
        >
          <input
            type="text"
            value={prompt}
            onChange={(event) =>
              setPrompt(event.target.value)
            }
            placeholder="Ask CyberTron..."
            disabled={reactorState === "THINKING"}
          />

          <button
            type="submit"
            disabled={reactorState === "THINKING"}
          >
            {reactorState === "THINKING"
              ? "PROCESSING"
              : "SEND"}
          </button>
        </form>

        <div className="response-panel">
          {responseText ? (
            <p>{responseText}</p>
          ) : (
            <p className="response-placeholder">
              C.O.R.E. awaiting input.
            </p>
          )}
        </div>
      </section>

      <section className="status-grid">
        <article>
          <span>CONTROL PLANE</span>
          <strong
            className={
              apiStatus === "ONLINE"
                ? "online"
                : ""
            }
          >
            {apiStatus}
          </strong>
        </article>

        <article>
          <span>EVENT BUS</span>
          <strong
            className={
              socketConnected
                ? "online"
                : ""
            }
          >
            {socketConnected
              ? "CONNECTED"
              : "OFFLINE"}
          </strong>
        </article>

        <article>
          <span>ACTIVE MODEL</span>
          <strong>{activeModel}</strong>
        </article>

        <article>
          <span>LAST EVENT</span>
          <strong>
            {lastEvent?.event_type ?? "WAITING"}
          </strong>
        </article>

        <article>
          <span>EVAL TOKENS</span>
          <strong>
            {evalCount ?? "—"}
          </strong>
        </article>

        <article>
          <span>MODEL DURATION</span>
          <strong>
            {durationMs !== null
              ? `${durationMs.toFixed(0)} ms`
              : "—"}
          </strong>
        </article>
      </section>

      <footer>
        Local-first AI orchestration control plane
      </footer>
    </main>
  );
}
