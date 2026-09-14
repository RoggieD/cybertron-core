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

function entityId(
  event: CoreEvent,
  type: "agent" | "tool" | "model" | "memory",
): string | null {
  if (event.target?.type === type) {
    const value = stringValue(event.target.id);
    if (value) return value;
  }

  if (event.actor?.type === type) {
    const value = stringValue(event.actor.id);
    if (value) return value;
  }

  return null;
}

function agentLabel(event: CoreEvent): string | null {
  return (
    stringValue(event.metadata?.agent_name) ??
    entityId(event, "agent")
  );
}

function modelLabel(event: CoreEvent): string | null {
  return (
    stringValue(event.metadata?.model) ??
    stringValue(event.metadata?.model_name) ??
    entityId(event, "model")
  );
}

function toolLabel(event: CoreEvent): string | null {
  return entityId(event, "tool");
}

function memoryLabel(event: CoreEvent): string {
  const scope = stringValue(event.metadata?.scope);
  const namespace = stringValue(event.metadata?.namespace);
  const kind = stringValue(event.metadata?.kind);
  const target = entityId(event, "memory");
  const detail = [scope, namespace, kind].filter(Boolean).join(" / ");

  return (
    detail ||
    target ||
    event.event_type.replace("memory.", "").replaceAll("_", " ").toUpperCase()
  );
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

function describeEvent(event: CoreEvent): string {
  const agent = agentLabel(event);
  const tool = toolLabel(event);
  const model = modelLabel(event);

  switch (event.event_type) {
    case "prompt.received":
      return "Prompt accepted by C.O.R.E.";
    case "router.started":
      return "Routing request to the best agent";
    case "agent.selected":
      return `Agent selected${agent ? `: ${agent}` : ""}`;
    case "agent.started":
      return `Agent active${agent ? `: ${agent}` : ""}`;
    case "agent.completed":
      return `Agent completed${agent ? `: ${agent}` : ""}`;
    case "tool.started":
      return `Tool execution started${tool ? `: ${tool}` : ""}`;
    case "tool.completed":
      return `Tool execution completed${tool ? `: ${tool}` : ""}`;
    case "model.request_started":
      return `Model inference started${model ? `: ${model}` : ""}`;
    case "model.token":
      return `Streaming response${model ? ` from ${model}` : ""}`;
    case "model.request_completed":
      return `Model inference completed${model ? `: ${model}` : ""}`;
    case "response.generated":
      return "Response delivered to user";
    case "model.error": {
      const error = stringValue(event.metadata?.error);
      return error ? `Model error: ${error}` : "Model inference error";
    }
    default:
      if (event.event_type.startsWith("memory.")) {
        const action = event.event_type
          .replace("memory.", "")
          .replaceAll("_", " ");
        return `Memory ${action}: ${memoryLabel(event)}`;
      }

      return event.event_type.replaceAll(".", " › ").replaceAll("_", " ");
  }
}

function appendTrail(current: CoreEvent[], event: CoreEvent): CoreEvent[] {
  if (
    event.event_type === "model.token" &&
    current[current.length - 1]?.event_type === "model.token"
  ) {
    return [...current.slice(0, -1), event].slice(-10);
  }

  return [...current, event].slice(-10);
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
          setEventTrail((current) => appendTrail(current, event));
          setEventCount((count) => count + 1);
          if (event.trace_id) setTraceId(event.trace_id);
        }

        const agent = agentLabel(event);
        if (agent && event.event_type.startsWith("agent.")) {
          setActiveAgent(agent);
        }

        const tool = toolLabel(event);
        if (tool && event.event_type.startsWith("tool.")) {
          setActiveTool(tool);
        }

        const model = modelLabel(event);
        if (model && event.event_type.startsWith("model.")) {
          setActiveModel(model);
        }

        if (event.event_type.startsWith("memory.")) {
          setMemoryAction(memoryLabel(event));
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

  const currentOperation = useMemo(
    () => (lastEvent ? describeEvent(lastEvent) : "Awaiting orchestration activity"),
    [lastEvent],
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
          <strong title={activeAgent}>{activeAgent}</strong>
        </article>
        <article>
          <span>ACTIVE TOOL</span>
          <strong title={activeTool}>{activeTool}</strong>
        </article>
        <article>
          <span>MEMORY</span>
          <strong title={memoryAction}>{memoryAction}</strong>
        </article>
        <article>
          <span>ACTIVE MODEL</span>
          <strong title={activeModel}>{activeModel}</strong>
        </article>
        <article>
          <span>TRACE ID</span>
          <strong className="trace-id" title={traceId ?? undefined}>{traceShort}</strong>
        </article>
        <article>
          <span>TRACE EVENTS</span>
          <strong>{eventCount}</strong>
        </article>
      </div>

      <div className={`processing-operation processing-operation-${stage.toLowerCase()}`}>
        <span>NOW PROCESSING</span>
        <strong>{currentOperation}</strong>
        <small>{lastEvent?.event_type ?? "core.idle"}</small>
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
                  <span>{describeEvent(event)}</span>
                  <small>
                    {event.event_type} · {new Date(event.timestamp).toLocaleTimeString()}
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
