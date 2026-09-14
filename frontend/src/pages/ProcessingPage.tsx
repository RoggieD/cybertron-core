import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import {
  connectCoreWebSocket,
  type CoreEvent,
} from "../api/websocket";

const CognitionGraph = lazy(
  () => import("../components/CognitionGraph"),
);

type ProcessingStage =
  | "IDLE"
  | "ROUTING"
  | "AGENT"
  | "MEMORY"
  | "TOOL"
  | "MODEL"
  | "COMPLETE"
  | "ERROR";

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function targetId(event: CoreEvent): string | null {
  return stringValue(event.target?.id);
}

function stageForEvent(eventType: string): ProcessingStage {
  if (eventType === "prompt.received" || eventType.startsWith("router.")) {
    return "ROUTING";
  }
  if (eventType.startsWith("agent.")) return "AGENT";
  if (eventType.startsWith("memory.")) return "MEMORY";
  if (eventType.startsWith("tool.")) return "TOOL";
  if (eventType.startsWith("model.")) {
    return eventType === "model.error" ? "ERROR" : "MODEL";
  }
  if (eventType === "response.generated") return "COMPLETE";
  return "IDLE";
}

function eventLabel(event: CoreEvent): string {
  const target = targetId(event);
  return target ? `${event.event_type} · ${target}` : event.event_type;
}

export default function ProcessingPage() {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<CoreEvent | null>(null);
  const [eventTrail, setEventTrail] = useState<CoreEvent[]>([]);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [eventCount, setEventCount] = useState(0);
  const [stage, setStage] = useState<ProcessingStage>("IDLE");
  const [activeAgent, setActiveAgent] = useState("NONE");
  const [activeTool, setActiveTool] = useState("NONE");
  const [activeModel, setActiveModel] = useState("UNKNOWN");
  const [memoryAction, setMemoryAction] = useState("IDLE");

  useEffect(() => {
    const socket = connectCoreWebSocket(
      (event) => {
        setLastEvent(event);
        setStage(stageForEvent(event.event_type));

        if (event.event_type === "prompt.received") {
          setEventTrail([event]);
          setEventCount(1);
          setTraceId(event.trace_id ?? null);
          setActiveAgent("ROUTING...");
          setActiveTool("NONE");
          setMemoryAction("IDLE");
        } else {
          setEventTrail((current) => [...current, event].slice(-10));
          setEventCount((count) => count + 1);
          if (event.trace_id) setTraceId(event.trace_id);
        }

        if (event.event_type === "agent.selected") {
          setActiveAgent(
            stringValue(event.metadata?.agent_name) ??
              targetId(event) ??
              "ACTIVE",
          );
        }

        if (event.event_type.startsWith("tool.")) {
          setActiveTool(targetId(event) ?? event.event_type.replace("tool.", ""));
        }

        if (event.event_type.startsWith("model.")) {
          setActiveModel(
            stringValue(event.metadata?.model) ??
              stringValue(event.metadata?.model_name) ??
              targetId(event) ??
              "ACTIVE",
          );
        }

        if (event.event_type.startsWith("memory.")) {
          setMemoryAction(
            targetId(event) ?? event.event_type.replace("memory.", "").toUpperCase(),
          );
        }

        if (event.event_type === "response.generated") {
          window.setTimeout(() => setStage("IDLE"), 1600);
        }
      },
      setConnected,
    );

    return () => socket.close();
  }, []);

  const traceShort = useMemo(
    () => (traceId ? traceId.slice(0, 12) : "—"),
    [traceId],
  );

  return (
    <section className="core-processing-page">
      <div className="core-processing-heading">
        <span>LIVE ORCHESTRATION</span>
        <h1>Processing Graph</h1>
        <p>
          Real-time cognition flow across routing, agents, memory,
          tools, and the active model.
        </p>
      </div>

      <div className="processing-status-grid">
        <article>
          <span>EVENT BUS</span>
          <strong className={connected ? "online" : "warning"}>
            {connected ? "CONNECTED" : "OFFLINE"}
          </strong>
        </article>
        <article>
          <span>CURRENT STAGE</span>
          <strong>{stage}</strong>
        </article>
        <article>
          <span>ACTIVE AGENT</span>
          <strong>{activeAgent}</strong>
        </article>
        <article>
          <span>ACTIVE TOOL</span>
          <strong>{activeTool}</strong>
        </article>
        <article>
          <span>MEMORY</span>
          <strong>{memoryAction}</strong>
        </article>
        <article>
          <span>ACTIVE MODEL</span>
          <strong>{activeModel}</strong>
        </article>
        <article>
          <span>TRACE ID</span>
          <strong className="trace-id">{traceShort}</strong>
        </article>
        <article>
          <span>TRACE EVENTS</span>
          <strong>{eventCount}</strong>
        </article>
      </div>

      <div className="core-processing-layout">
        <div className="core-processing-graph">
          <Suspense
            fallback={
              <div className="core-graph-loading">
                INITIALIZING COGNITION MAP…
              </div>
            }
          >
            <CognitionGraph event={lastEvent} connected={connected} />
          </Suspense>
        </div>

        <aside className="processing-event-trail">
          <div className="processing-event-trail-header">
            <span>LIVE EVENT TRAIL</span>
            <strong>{eventTrail.length}/10</strong>
          </div>

          <div className="processing-event-list">
            {eventTrail.length === 0 ? (
              <div className="processing-event-empty">
                Awaiting orchestration activity…
              </div>
            ) : (
              [...eventTrail].reverse().map((event) => (
                <div className="processing-event-item" key={event.event_id}>
                  <span>{eventLabel(event)}</span>
                  <small>
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </small>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}
