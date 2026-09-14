import { FormEvent, useEffect, useState } from "react";

import { getHealth } from "./api/core";
import {
  getStatusOverview,
  getServiceStatus,
  type StatusOverview,
  type ServiceHealthItem
} from "./api/status";
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
  | "TOOL_ACTIVE"
  | "THINKING"
  | "COMPLETE"
  | "ERROR";

type TelemetryState =
  | "HEALTHY"
  | "ELEVATED"
  | "WARNING";

function getTelemetryState(
  overview: StatusOverview | null,
  error: boolean
): TelemetryState {
  if (error) {
    return "WARNING";
  }

  if (!overview) {
    return "HEALTHY";
  }

  if (
    overview.services.unreachable > 0 ||
    overview.system.disk.usage_percent >= 95
  ) {
    return "WARNING";
  }

  if (
    overview.system.cpu.usage_percent >= 75 ||
    overview.system.memory.usage_percent >= 80 ||
    overview.system.disk.usage_percent >= 85
  ) {
    return "ELEVATED";
  }

  return "HEALTHY";
}


function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours >= 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }

  return `${hours}h ${minutes}m`;
}

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
  const [activeTool, setActiveTool] = useState("NONE");

  const [evalCount, setEvalCount] = useState<number | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);

  const [traceId, setTraceId] = useState<string | null>(null);
  const [traceEventCount, setTraceEventCount] = useState(0);

  const [overview, setOverview] =
    useState<StatusOverview | null>(null);
  const [overviewError, setOverviewError] = useState(false);
  const [services, setServices] = useState<ServiceHealthItem[]>([]);
  const [selectedService, setSelectedService] =
    useState<ServiceHealthItem | null>(null);
  const [manualCheckBusy, setManualCheckBusy] = useState(false);
  const [lastManualCheck, setLastManualCheck] =
    useState<Date | null>(null);

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      try {
        const [data, serviceData] = await Promise.all([
          getStatusOverview(),
          getServiceStatus()
        ]);

        if (active) {
          setOverview(data);
          setServices(serviceData.services);
          setOverviewError(false);

          setSelectedService((current) => {
            if (!current) {
              return null;
            }

            return (
              serviceData.services.find(
                (service) => service.name === current.name
              ) ?? current
            );
          });
        }
      } catch {
        if (active) {
          setOverviewError(true);
        }
      }
    };

    void refresh();

    const timer = window.setInterval(
      () => void refresh(),
      5000
    );

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

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

          case "tool.started": {
            const toolId = event.target?.id;

            if (typeof toolId === "string") {
              setActiveTool(toolId);
            }

            setReactorState("TOOL_ACTIVE");
            break;
          }

          case "tool.completed":
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

  async function checkSelectedService() {
    if (!selectedService || manualCheckBusy) {
      return;
    }

    setManualCheckBusy(true);

    try {
      const serviceData = await getServiceStatus();

      setServices(serviceData.services);

      const refreshed =
        serviceData.services.find(
          (service) =>
            service.name === selectedService.name
        ) ?? selectedService;

      setSelectedService(refreshed);
      setLastManualCheck(new Date());
      setOverviewError(false);
    } catch {
      setOverviewError(true);
    } finally {
      setManualCheckBusy(false);
    }
  }

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
    setActiveTool("NONE");
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
            setActiveModel("NOT USED");
            setEvalCount(null);
            setDurationMs(null);
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

  const telemetryState = getTelemetryState(
    overview,
    overviewError
  );

  const busy =
    reactorState === "ROUTING" ||
    reactorState === "AGENT_ACTIVE" ||
    reactorState === "TOOL_ACTIVE" ||
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
        className={`reactor-panel reactor-${reactorState.toLowerCase()} telemetry-${telemetryState.toLowerCase()}`}
      >
        <div className="reactor">
          <div className="reactor-core" />
          <div className="reactor-ring ring-one" />
          <div className="reactor-ring ring-two" />
          <div className="reactor-ring ring-three" />
        </div>

        <div className="state-label">
          {reactorState}
          {reactorState === "IDLE" && (
            <span className={`reactor-health telemetry-${telemetryState.toLowerCase()}`}>
              {" "}• {telemetryState}
            </span>
          )}
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

      <section className="telemetry-panel">
        <div className="telemetry-header">
          <div>
            <span>LIVE SYSTEM TELEMETRY</span>
            <strong>
              {overview?.system.hostname ?? "ACQUIRING..."}
            </strong>
          </div>

          <div
            className={`telemetry-state telemetry-${telemetryState.toLowerCase()}`}
          >
            {overviewError
              ? "LINK ERROR"
              : telemetryState}
          </div>
        </div>

        <div className="telemetry-grid">
          <article className="telemetry-card">
            <span>CPU</span>
            <strong>
              {overview
                ? `${overview.system.cpu.usage_percent}%`
                : "--"}
            </strong>
            <div className="meter">
              <div
                style={{
                  width: `${overview?.system.cpu.usage_percent ?? 0}%`
                }}
              />
            </div>
          </article>

          <article className="telemetry-card">
            <span>MEMORY</span>
            <strong>
              {overview
                ? `${overview.system.memory.usage_percent}%`
                : "--"}
            </strong>
            <div className="meter">
              <div
                style={{
                  width: `${overview?.system.memory.usage_percent ?? 0}%`
                }}
              />
            </div>
          </article>

          <article className="telemetry-card">
            <span>DISK</span>
            <strong>
              {overview
                ? `${overview.system.disk.usage_percent}%`
                : "--"}
            </strong>
            <div className="meter">
              <div
                style={{
                  width: `${overview?.system.disk.usage_percent ?? 0}%`
                }}
              />
            </div>
          </article>

          <article className="telemetry-card">
            <span>UPTIME</span>
            <strong>
              {overview
                ? formatUptime(overview.system.uptime_seconds)
                : "--"}
            </strong>
          </article>

          <article className="telemetry-card">
            <span>DOCKER</span>
            <strong>
              {overview
                ? `${overview.docker.running}/${overview.docker.total}`
                : "--"}
            </strong>
            <small>RUNNING</small>
          </article>

          <article className="telemetry-card">
            <span>SERVICES</span>
            <strong
              className={
                overview?.services.unreachable === 0
                  ? "online"
                  : "warning"
              }
            >
              {overview
                ? `${overview.services.reachable}/${overview.services.total}`
                : "--"}
            </strong>
            <small>HEALTHY</small>
          </article>

          <article className="telemetry-card">
            <span>LISTENERS</span>
            <strong>
              {overview?.network.listeners ?? "--"}
            </strong>
            <small>ACTIVE SOCKETS</small>
          </article>
        </div>
      </section>

      <section className="service-health-panel">
        <div className="service-health-header">
          <div>
            <span>SERVICE MATRIX</span>
            <strong>
              {overview
                ? `${overview.services.reachable}/${overview.services.total} OPERATIONAL`
                : "ACQUIRING..."}
            </strong>
          </div>
        </div>

        <div className="service-card-grid">
          {services.map((service) => (
            <button
              type="button"
              key={service.name}
              className={`service-card ${
                service.reachable
                  ? "service-up"
                  : "service-down"
              } ${
                selectedService?.name === service.name
                  ? "selected"
                  : ""
              }`}
              onClick={() => setSelectedService(service)}
            >
              <span>{service.name}</span>

              <strong>
                {service.reachable ? "ONLINE" : "OFFLINE"}
              </strong>

              <small>
                {service.scope.toUpperCase()}
                {typeof service.latency_ms === "number"
                  ? ` • ${service.latency_ms} ms`
                  : ""}
              </small>
            </button>
          ))}
        </div>

        {selectedService && (
          <div className="service-detail">
            <div className="service-detail-heading">
              <div>
                <span>SELECTED SERVICE</span>
                <strong>{selectedService.name}</strong>
              </div>

              <div className="service-detail-actions">
                <button
                  type="button"
                  onClick={() => void checkSelectedService()}
                  disabled={manualCheckBusy}
                >
                  {manualCheckBusy ? "CHECKING..." : "CHECK NOW"}
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedService(null)}
                >
                  CLOSE
                </button>
              </div>
            </div>

            <div className="service-detail-grid">
              <div>
                <span>STATE</span>
                <strong
                  className={
                    selectedService.reachable
                      ? "online"
                      : "warning"
                  }
                >
                  {selectedService.reachable
                    ? "ONLINE"
                    : "OFFLINE"}
                </strong>
              </div>

              <div>
                <span>SCOPE</span>
                <strong>
                  {selectedService.scope.toUpperCase()}
                </strong>
              </div>

              <div>
                <span>HTTP</span>
                <strong>
                  {selectedService.status_code ?? "N/A"}
                </strong>
              </div>

              <div>
                <span>LATENCY</span>
                <strong>
                  {typeof selectedService.latency_ms === "number"
                    ? `${selectedService.latency_ms} ms`
                    : "N/A"}
                </strong>
              </div>
            </div>

            <div className="service-target">
              <span>TARGET</span>
              <code>
                {selectedService.target ?? "Not reported"}
              </code>
            </div>

            <div className="service-last-check">
              <span>LAST MANUAL CHECK</span>
              <strong>
                {lastManualCheck
                  ? lastManualCheck.toLocaleTimeString()
                  : "NOT RUN"}
              </strong>
            </div>

            {selectedService.error && (
              <div className="service-error">
                {selectedService.error}
              </div>
            )}
          </div>
        )}
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
          <span>ACTIVE TOOL</span>
          <strong>{activeTool}</strong>
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
