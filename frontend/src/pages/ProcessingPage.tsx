import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import type { TraceDetail } from "../api/traces";
import {
  connectCoreWebSocket,
  type CoreEvent,
} from "../api/websocket";
import TraceReplayPanel from "../components/TraceReplayPanel";

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

type ProvenanceState = {
  userInput: boolean;
  agent: string;
  memoryCount: number | null;
  memoryScopes: string[];
  memoryKinds: string[];
  memorySources: string[];
  memoryNamespaces: string[];
  tools: string[];
  model: string;
};

const EMPTY_PROVENANCE: ProvenanceState = {
  userInput: false,
  agent: "NONE",
  memoryCount: null,
  memoryScopes: [],
  memoryKinds: [],
  memorySources: [],
  memoryNamespaces: [],
  tools: [],
  model: "UNKNOWN",
};

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is string => typeof item === "string" && !!item.trim(),
  );
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
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
  return stringValue(event.metadata?.agent_name) ?? entityId(event, "agent");
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

function joinValues(values: string[], empty = "NONE"): string {
  return values.length ? values.join(", ") : empty;
}

function provenanceForEvent(current: ProvenanceState, event: CoreEvent): ProvenanceState {
  let next = current;

  if (event.event_type === "prompt.received") {
    next = { ...next, userInput: true };
  }

  const agent = agentLabel(event);
  if (agent && event.event_type.startsWith("agent.")) {
    next = { ...next, agent };
  }

  const tool = toolLabel(event);
  if (tool && event.event_type.startsWith("tool.")) {
    next = {
      ...next,
      tools: next.tools.includes(tool) ? next.tools : [...next.tools, tool],
    };
  }

  const model = modelLabel(event);
  if (model && event.event_type.startsWith("model.")) {
    next = { ...next, model };
  }

  if (event.event_type === "memory.search_completed") {
    const resultCount = numberValue(event.metadata?.result_count);
    const scopes = stringList(event.metadata?.scopes);
    const kinds = stringList(event.metadata?.kinds);
    const sources = stringList(event.metadata?.sources);
    const namespaces = stringList(event.metadata?.namespaces);
    const fallbackScope = stringValue(event.metadata?.scope);

    next = {
      ...next,
      memoryCount: resultCount,
      memoryScopes: scopes.length
        ? scopes
        : fallbackScope && fallbackScope !== "none"
          ? fallbackScope.split(",").map((value) => value.trim()).filter(Boolean)
          : [],
      memoryKinds: kinds,
      memorySources: sources,
      memoryNamespaces: namespaces,
    };
  }

  return next;
}

function provenanceForEvents(events: CoreEvent[]): ProvenanceState {
  return events.reduce(provenanceForEvent, { ...EMPTY_PROVENANCE });
}

function latestLabel(events: CoreEvent[], getter: (event: CoreEvent) => string | null, fallback: string): string {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const value = getter(events[index]);
    if (value) return value;
  }
  return fallback;
}

function replayableEvents(events: CoreEvent[]): CoreEvent[] {
  return events.filter(
    (event, index) =>
      event.event_type !== "model.token" ||
      index === 0 ||
      events[index - 1].event_type !== "model.token",
  );
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
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
  const [provenance, setProvenance] = useState<ProvenanceState>(EMPTY_PROVENANCE);
  const [replaying, setReplaying] = useState(false);
  const [viewMode, setViewMode] = useState<"LIVE" | "INSPECT" | "REPLAY">("LIVE");

  useEffect(() => {
    const socket = connectCoreWebSocket(
      (event) => {
        if (replaying) return;

        setViewMode("LIVE");
        setLastEvent(event);
        setStage(stageForEvent(event.event_type));

        if (event.event_type === "prompt.received") {
          setEventTrail([event]);
          setEventCount(1);
          setTraceId(event.trace_id ?? null);
          setActiveAgent("ROUTING...");
          setActiveTool("NONE");
          setMemoryAction("IDLE");
          setProvenance({ ...EMPTY_PROVENANCE, userInput: true });
        } else {
          setEventTrail((current) => appendTrail(current, event));
          setEventCount((count) => count + 1);
          if (event.trace_id) setTraceId(event.trace_id);
          setProvenance((current) => provenanceForEvent(current, event));
        }

        const agent = agentLabel(event);
        if (agent && event.event_type.startsWith("agent.")) setActiveAgent(agent);

        const tool = toolLabel(event);
        if (tool && event.event_type.startsWith("tool.")) setActiveTool(tool);

        const model = modelLabel(event);
        if (model && event.event_type.startsWith("model.")) setActiveModel(model);

        if (event.event_type.startsWith("memory.")) setMemoryAction(memoryLabel(event));

        if (event.event_type === "response.generated") {
          window.setTimeout(() => setStage("IDLE"), 1600);
        }
      },
      setConnected,
    );

    return () => socket.close();
  }, [replaying]);

  function inspectTrace(trace: TraceDetail) {
    const events = trace.events;
    const finalEvent = events.at(-1) ?? null;
    setViewMode("INSPECT");
    setTraceId(trace.trace_id);
    setEventCount(trace.count);
    setEventTrail(events.slice(-10));
    setLastEvent(finalEvent);
    setStage(trace.errored ? "ERROR" : trace.completed ? "COMPLETE" : finalEvent ? stageForEvent(finalEvent.event_type) : "IDLE");
    setActiveAgent(latestLabel(events, agentLabel, "NONE"));
    setActiveTool(latestLabel(events, toolLabel, "NONE"));
    setActiveModel(latestLabel(events, modelLabel, "UNKNOWN"));
    const memoryEvent = [...events].reverse().find((event) => event.event_type.startsWith("memory."));
    setMemoryAction(memoryEvent ? memoryLabel(memoryEvent) : "IDLE");
    setProvenance(provenanceForEvents(events));
  }

  async function replayTrace(trace: TraceDetail) {
    setReplaying(true);
    setViewMode("REPLAY");
    setTraceId(trace.trace_id);
    setEventTrail([]);
    setEventCount(0);
    setLastEvent(null);
    setStage("IDLE");
    setActiveAgent("NONE");
    setActiveTool("NONE");
    setActiveModel("UNKNOWN");
    setMemoryAction("IDLE");
    setProvenance({ ...EMPTY_PROVENANCE });

    let replayProvenance = { ...EMPTY_PROVENANCE };
    const events = replayableEvents(trace.events);

    for (let index = 0; index < events.length; index += 1) {
      const event = events[index];
      replayProvenance = provenanceForEvent(replayProvenance, event);
      setProvenance(replayProvenance);
      setLastEvent(event);
      setStage(stageForEvent(event.event_type));
      setEventTrail((current) => appendTrail(current, event));
      setEventCount(index + 1);

      const agent = agentLabel(event);
      if (agent && event.event_type.startsWith("agent.")) setActiveAgent(agent);
      const tool = toolLabel(event);
      if (tool && event.event_type.startsWith("tool.")) setActiveTool(tool);
      const model = modelLabel(event);
      if (model && event.event_type.startsWith("model.")) setActiveModel(model);
      if (event.event_type.startsWith("memory.")) setMemoryAction(memoryLabel(event));

      await delay(event.event_type === "model.token" ? 500 : 360);
    }

    setEventCount(trace.count);
    setReplaying(false);
  }

  const traceShort = useMemo(
    () => (traceId ? traceId.slice(0, 12) : "—"),
    [traceId],
  );

  const currentOperation = useMemo(
    () => lastEvent ? describeEvent(lastEvent) : "Awaiting orchestration activity",
    [lastEvent],
  );

  return (
    <section className="core-processing-page">
      <div className="core-processing-heading">
        <span>LIVE ORCHESTRATION</span>
        <h1>Processing Graph</h1>
        <p>
          Real-time cognition flow, information provenance, routing,
          agents, memory, tools, and active-model execution.
        </p>
      </div>

      <div className="core-processing-graph" style={{ marginBottom: 12 }}>
        <Suspense fallback={<div className="core-graph-loading">INITIALIZING COGNITION MAP…</div>}>
          <CognitionGraph
            event={lastEvent}
            connected={connected}
            provenance={{
              memorySources: provenance.memorySources,
              tools: provenance.tools,
            }}
          />
        </Suspense>
      </div>

      <div className={`processing-operation processing-operation-${stage.toLowerCase()}`}>
        <span>{viewMode === "LIVE" ? "NOW PROCESSING" : `${viewMode} TRACE`}</span>
        <strong>{currentOperation}</strong>
        <small>{lastEvent?.event_type ?? "core.idle"}</small>
      </div>

      <section className="processing-provenance" aria-label="Model information provenance">
        <div className="processing-provenance-header">
          <div>
            <span>INFORMATION PROVENANCE</span>
            <strong>What is feeding the model?</strong>
          </div>
          <small>TRACE {traceShort}</small>
        </div>

        <div className="processing-provenance-flow">
          <article className={provenance.userInput ? "active" : ""}>
            <span>USER INPUT</span>
            <strong>{provenance.userInput ? "PRESENT" : "WAITING"}</strong>
            <small>Prompt content is not mirrored into telemetry.</small>
          </article>
          <article className={provenance.agent !== "NONE" ? "active" : ""}>
            <span>AGENT / POLICY</span>
            <strong title={provenance.agent}>{provenance.agent}</strong>
            <small>Selected orchestration authority.</small>
          </article>
          <article className={provenance.memoryCount !== null ? "active" : ""}>
            <span>PERSISTENT MEMORY</span>
            <strong>{provenance.memoryCount === null ? "NOT QUERIED" : `${provenance.memoryCount} RECORD${provenance.memoryCount === 1 ? "" : "S"}`}</strong>
            <small>Scopes: {joinValues(provenance.memoryScopes)}</small>
          </article>
          <article className={provenance.tools.length ? "active" : ""}>
            <span>TOOLS / LIVE DATA</span>
            <strong title={joinValues(provenance.tools)}>{joinValues(provenance.tools)}</strong>
            <small>Verified runtime and external evidence path.</small>
          </article>
          <article className={provenance.model !== "UNKNOWN" ? "active" : ""}>
            <span>MODEL</span>
            <strong title={provenance.model}>{provenance.model}</strong>
            <small>Inference destination for assembled context.</small>
          </article>
        </div>

        <div className="processing-provenance-detail">
          <div><span>MEMORY SOURCES</span><strong title={joinValues(provenance.memorySources)}>{joinValues(provenance.memorySources)}</strong></div>
          <div><span>MEMORY KINDS</span><strong title={joinValues(provenance.memoryKinds)}>{joinValues(provenance.memoryKinds)}</strong></div>
          <div><span>NAMESPACES</span><strong title={joinValues(provenance.memoryNamespaces)}>{joinValues(provenance.memoryNamespaces)}</strong></div>
          <div><span>EVIDENCE CHANNELS</span><strong>{[
            provenance.userInput ? "USER" : null,
            provenance.memoryCount !== null ? "MEMORY" : null,
            provenance.tools.length ? "TOOLS" : null,
          ].filter(Boolean).join(" + ") || "NONE"}</strong></div>
        </div>
      </section>

      <div className="processing-status-grid">
        <article><span>EVENT BUS</span><strong className={connected ? "online" : "warning"}>{connected ? "CONNECTED" : "OFFLINE"}</strong></article>
        <article><span>CURRENT STAGE</span><strong>{replaying ? "REPLAY" : stage}</strong></article>
        <article><span>ACTIVE AGENT</span><strong title={activeAgent}>{activeAgent}</strong></article>
        <article><span>ACTIVE TOOL</span><strong title={activeTool}>{activeTool}</strong></article>
        <article><span>MEMORY</span><strong title={memoryAction}>{memoryAction}</strong></article>
        <article><span>ACTIVE MODEL</span><strong title={activeModel}>{activeModel}</strong></article>
        <article><span>TRACE ID</span><strong className="trace-id" title={traceId ?? undefined}>{traceShort}</strong></article>
        <article><span>TRACE EVENTS</span><strong>{eventCount}</strong></article>
      </div>

      <aside className="processing-event-trail" style={{ width: "100%" }}>
        <div className="processing-event-trail-header">
          <span>{viewMode === "LIVE" ? "LIVE EVENT TRAIL" : `${viewMode} EVENT TRAIL`}</span>
          <strong>{eventTrail.length}/10</strong>
        </div>
        <div className="processing-event-list">
          {eventTrail.length === 0 ? (
            <div className="processing-event-empty">Awaiting orchestration activity…</div>
          ) : (
            [...eventTrail].reverse().map((event) => (
              <div className="processing-event-item" key={event.event_id}>
                <span>{describeEvent(event)}</span>
                <small>{event.event_type} · {new Date(event.timestamp).toLocaleTimeString()}</small>
              </div>
            ))
          )}
        </div>
      </aside>

      <TraceReplayPanel onLoad={inspectTrace} onReplay={replayTrace} replaying={replaying} />
    </section>
  );
}
