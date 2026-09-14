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
  | "ROUTING"
  | "AGENT_ACTIVE"
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
  const [activeAgent, setActiveAgent] = useState("NONE");

  const [evalCount, setEvalCount] = useState<number | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);

  const [traceId, setTraceId] = useState<string | null>(null);
  const [traceEventCount, setTraceEventCount] = useState(0);

  useEffect(() => {
    void getHealth()
      .then(() => setApiStatus("ONLINE"))
      .catch(() => setApiStatus("OFFLINE"));

    const socket = connectCoreWebSocket(
      (event) => {
        setLastEvent(event);

        if (event.trace_id) {
          setTraceId(event.trace_id);
          setTraceEventCount((count) => count + 1);
        }

        switch (event.event_type) {
          case "prompt.received":
          case "router.started":
            setReactorState("ROUTING");
            break;

          case "agent.selected": {
            const agentName = event.metadata?.agent_name;

            if (typeof agentName === "string") {
              setActiveAgent(agentName);
            } else {
              const agentId = event.target?.id;

              if (typeof agentId === "string") {
                setActiveAgent(agentId);
              }
            }

            setReactorState("AGENT_ACTIVE");
            break;
          }

          case "agent.started":
            setReactorState("AGENT_ACTIVE");
            break;

          case "model.request_started":
          case "model.token":
            setReactorState("THINKING");
            break;

          case "model.request_completed":
          case "agent.completed":
            setReactorState("COMPLETE");
            break;

          case "response.generated":
            window.setTimeout(() => {
              setReactorState("IDLE");
            }, 1200);
            break;

          case "model.error":
            setReactorState("ERROR");
            break;
        }
      },
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
    setTraceId(null);
    setTraceEventCount(0);
    setActiveAgent("ROUTING...");
    setReactorState("ROUTING");

    try {
      await streamChat(
        message,
        (streamEvent: StreamEvent) => {
          if (streamEvent.model) {
            setActiveModel(streamEvent.model);
          }

          const eventWithAgent = streamEvent as StreamEvent & {
            agent_name?: string;
            agent?: string;
          };

          if (eventWithAgent.agent_name) {
            setActiveAgent(eventWithAgent.agent_name);
          } else if (eventWithAgent.agent) {
            setActiveAgent(eventWithAgent.agent);
          }

          if (
            streamEvent.event === "tool.result" &&
            streamEvent.content
          ) {
            setResponseText(streamEvent.content);
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

  const busy =
    reactorState === "ROUTING" ||
    reactorState === "AGENT_ACTIVE" ||
    reactorState === "THINKING";

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
            disabled={busy}
          />

          <button
            type="submit"
            disabled={busy}
          >
            {busy ? "PROCESSING" : "SEND"}
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
          <strong className={apiStatus === "ONLINE" ? "online" : ""}>
            {apiStatus}
          </strong>
        </article>

        <article>
          <span>EVENT BUS</span>
          <strong className={socketConnected ? "online" : ""}>
            {socketConnected ? "CONNECTED" : "OFFLINE"}
          </strong>
        </article>

        <article>
          <span>ACTIVE MODEL</span>
          <strong>{activeModel}</strong>
        </article>

        <article>
          <span>ACTIVE AGENT</span>
          <strong>{activeAgent}</strong>
        </article>

        <article>
          <span>ACTIVE EVENT</span>
          <strong>
            {lastEvent?.event_type ?? "WAITING"}
          </strong>
        </article>

        <article>
          <span>TRACE EVENTS</span>
          <strong>{traceEventCount}</strong>
        </article>

        <article>
          <span>TRACE ID</span>
          <strong className="trace-id">
            {traceId ? traceId.slice(0, 8) : "—"}
          </strong>
        </article>

        <article>
          <span>EVAL TOKENS</span>
          <strong>{evalCount ?? "—"}</strong>
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
