import InfrastructureExplorer from "../components/InfrastructureExplorer";
import { useEffect, useState } from "react";

import {
  getServiceStatus,
  getStatusOverview,
  getTelemetryHistory,
  type StatusOverview,
} from "../api/status";
import {
  getSecurityPolicyEvaluation,
  type SecurityPolicyEvaluation,
} from "../api/security";

import "../styles.css";
import "../security-policy.css";

type TelemetrySample = {
  timestamp: number;
  cpu: number;
  memory: number;
  disk: number;
  gpu: number | null;
  gpuMemory: number | null;
  gpuPower: number | null;
  serviceLatency: number;
};

type TelemetryRange = "2m" | "15m" | "1h" | "24h";

const TELEMETRY_RANGES = {
  "2m": { label: "2 MIN", milliseconds: 2 * 60 * 1000, historyLimit: 8 },
  "15m": { label: "15 MIN", milliseconds: 15 * 60 * 1000, historyLimit: 60 },
  "1h": { label: "1 HOUR", milliseconds: 60 * 60 * 1000, historyLimit: 240 },
  "24h": { label: "24 HOUR", milliseconds: 24 * 60 * 60 * 1000, historyLimit: 5760 },
} as const;

function Sparkline({ values, maxValue = 100 }: { values: number[]; maxValue?: number }) {
  if (values.length < 2) {
    return <div className="sparkline-empty">ACQUIRING DATA</div>;
  }

  const width = 240;
  const height = 56;
  const effectiveMax = Math.max(maxValue, ...values, 1);
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - Math.min(value / effectiveMax, 1) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      className="sparkline"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={points} />
    </svg>
  );
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

function formatGb(megabytes?: number | null): string {
  if (typeof megabytes !== "number") return "--";
  return (megabytes / 1024).toFixed(1);
}

function EndpointList({ endpoints }: { endpoints: string[] }) {
  if (!endpoints.length) return <small>NONE DETECTED</small>;

  return (
    <ul>
      {endpoints.map((endpoint) => (
        <li key={endpoint}>{endpoint}</li>
      ))}
    </ul>
  );
}

export default function SystemsPage() {
  const [overview, setOverview] = useState<StatusOverview | null>(null);
  const [overviewError, setOverviewError] = useState(false);
  const [telemetryHistory, setTelemetryHistory] = useState<TelemetrySample[]>([]);
  const [telemetryRange, setTelemetryRange] = useState<TelemetryRange>("2m");
  const [securityPolicy, setSecurityPolicy] = useState<SecurityPolicyEvaluation | null>(null);
  const [securityPolicyError, setSecurityPolicyError] = useState(false);

  useEffect(() => {
    let active = true;
    const range = TELEMETRY_RANGES[telemetryRange];
    const cutoff = Date.now() - range.milliseconds;

    void getTelemetryHistory(range.historyLimit)
      .then((history) => {
        if (!active) return;

        setTelemetryHistory(
          history.samples
            .map((sample) => ({
              timestamp: new Date(sample.timestamp).getTime(),
              cpu: sample.cpu_percent,
              memory: sample.memory_percent,
              disk: sample.disk_percent,
              gpu: typeof sample.gpu_percent === "number" ? sample.gpu_percent : null,
              gpuMemory: typeof sample.gpu_memory_percent === "number" ? sample.gpu_memory_percent : null,
              gpuPower: typeof sample.gpu_power_watts === "number" ? sample.gpu_power_watts : null,
              serviceLatency: sample.service_latency_ms,
            }))
            .filter((sample) => sample.timestamp >= cutoff),
        );
      })
      .catch(() => {
        // Live telemetry continues if persisted history is unavailable.
      });

    return () => {
      active = false;
    };
  }, [telemetryRange]);

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      try {
        const [data, serviceData] = await Promise.all([
          getStatusOverview(),
          getServiceStatus(),
        ]);

        if (!active) return;

        setOverview(data);
        setOverviewError(false);

        try {
          const policy = await getSecurityPolicyEvaluation(data.system.hostname);
          if (active) {
            setSecurityPolicy(policy);
            setSecurityPolicyError(false);
          }
        } catch {
          if (active) setSecurityPolicyError(true);
        }

        const latencyValues = serviceData.services
          .map((service) => service.latency_ms)
          .filter((value): value is number => typeof value === "number");

        const averageLatency = latencyValues.length
          ? latencyValues.reduce((sum, value) => sum + value, 0) / latencyValues.length
          : 0;

        setTelemetryHistory((current) => {
          const now = Date.now();
          const cutoff = now - TELEMETRY_RANGES[telemetryRange].milliseconds;
          const gpu = data.system.gpu;

          return [
            ...current,
            {
              timestamp: now,
              cpu: data.system.cpu.usage_percent,
              memory: data.system.memory.usage_percent,
              disk: data.system.disk.usage_percent,
              gpu: gpu?.available && typeof gpu.usage_percent === "number" ? gpu.usage_percent : null,
              gpuMemory: gpu?.available && typeof gpu.memory_usage_percent === "number" ? gpu.memory_usage_percent : null,
              gpuPower: gpu?.available && typeof gpu.power_draw_watts === "number" ? gpu.power_draw_watts : null,
              serviceLatency: averageLatency,
            },
          ].filter((sample) => sample.timestamp >= cutoff);
        });
      } catch {
        if (active) setOverviewError(true);
      }
    };

    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [telemetryRange]);

  const unexpected = securityPolicy?.unexpected_public_listener_endpoints ?? [];
  const missing = securityPolicy?.missing_approved_public_listener_endpoints ?? [];
  const approved = securityPolicy?.approved_public_listener_endpoints ?? [];
  const policyState = securityPolicyError
    ? "POLICY LINK ERROR"
    : !securityPolicy
      ? "ACQUIRING"
      : unexpected.length
        ? "POLICY DRIFT"
        : missing.length
          ? "SERVICE DRIFT"
          : securityPolicy.approved_configured
            ? "APPROVED / CLEAN"
            : "LEARNED ONLY";
  const policyStateClass = securityPolicyError || unexpected.length
    ? "alert"
    : missing.length || !securityPolicy?.approved_configured
      ? "warning"
      : "approved";

  const gpuValues = telemetryHistory
    .map((sample) => sample.gpu)
    .filter((value): value is number => typeof value === "number");
  const gpuMemoryValues = telemetryHistory
    .map((sample) => sample.gpuMemory)
    .filter((value): value is number => typeof value === "number");
  const currentGpu = overview?.system.gpu;

  return (
    <main className="core-shell">
      <section className="header">
        <p className="eyebrow">SYSTEM INTELLIGENCE</p>
        <h1>
          C.O.R.E. <span>Systems</span>
        </h1>
        <p className="subtitle">Host telemetry, capacity, runtime health, and infrastructure trends</p>
      </section>

      <InfrastructureExplorer />

      <section className="telemetry-panel">
        <div className="telemetry-header">
          <div>
            <span>LIVE SYSTEM TELEMETRY</span>
            <strong>{overview?.system.hostname ?? "ACQUIRING..."}</strong>
          </div>

          <div className={`telemetry-state ${overviewError ? "telemetry-warning" : "telemetry-healthy"}`}>
            {overviewError ? "LINK ERROR" : "ONLINE"}
          </div>
        </div>

        <div className="telemetry-grid" style={{ gridTemplateColumns: "repeat(8, minmax(100px, 1fr))" }}>
          <article className="telemetry-card">
            <span>CPU</span>
            <strong>{overview ? `${overview.system.cpu.usage_percent}%` : "--"}</strong>
            <div className="meter"><div style={{ width: `${overview?.system.cpu.usage_percent ?? 0}%` }} /></div>
          </article>

          <article className="telemetry-card">
            <span>MEMORY</span>
            <strong>{overview ? `${overview.system.memory.usage_percent}%` : "--"}</strong>
            <div className="meter"><div style={{ width: `${overview?.system.memory.usage_percent ?? 0}%` }} /></div>
          </article>

          <article className="telemetry-card">
            <span>VRAM</span>
            <strong>
              {currentGpu?.available && typeof currentGpu.memory_usage_percent === "number"
                ? `${currentGpu.memory_usage_percent}%`
                : "N/A"}
            </strong>
            <div className="meter">
              <div style={{ width: `${currentGpu?.memory_usage_percent ?? 0}%` }} />
            </div>
            <small>
              {currentGpu?.available
                ? `${formatGb(currentGpu.memory_used_mb)} / ${formatGb(currentGpu.memory_total_mb)} GB`
                : "GPU UNAVAILABLE"}
            </small>
          </article>

          <article className="telemetry-card">
            <span>DISK</span>
            <strong>{overview ? `${overview.system.disk.usage_percent}%` : "--"}</strong>
            <div className="meter"><div style={{ width: `${overview?.system.disk.usage_percent ?? 0}%` }} /></div>
          </article>

          <article className="telemetry-card">
            <span>UPTIME</span>
            <strong>{overview ? formatUptime(overview.system.uptime_seconds) : "--"}</strong>
          </article>

          <article className="telemetry-card">
            <span>DOCKER</span>
            <strong>{overview ? `${overview.docker.running}/${overview.docker.total}` : "--"}</strong>
            <small>RUNNING</small>
          </article>

          <article className="telemetry-card">
            <span>SERVICES</span>
            <strong className={overview?.services.unreachable === 0 ? "online" : "warning"}>
              {overview ? `${overview.services.reachable}/${overview.services.total}` : "--"}
            </strong>
            <small>HEALTHY</small>
          </article>

          <article className="telemetry-card">
            <span>LISTENERS</span>
            <strong>{overview?.network.listeners ?? "--"}</strong>
            <small>ACTIVE SOCKETS</small>
          </article>
        </div>
      </section>

      <section className="security-policy-panel">
        <div className="security-policy-header">
          <div>
            <span>DEFENSIVE LISTENER POLICY</span>
            <strong>{securityPolicy?.hostname ?? overview?.system.hostname ?? "ACQUIRING..."}</strong>
          </div>
          <div className={`security-policy-state ${policyStateClass}`}>{policyState}</div>
        </div>

        <div className="security-policy-grid">
          <article className="security-policy-card">
            <span>APPROVED PUBLIC LISTENERS</span>
            <strong>{securityPolicy?.approved_public_listener_count ?? "--"}</strong>
            <EndpointList endpoints={approved} />
          </article>

          <article className="security-policy-card unexpected">
            <span>UNEXPECTED PUBLIC LISTENERS</span>
            <strong>{unexpected.length}</strong>
            <EndpointList endpoints={unexpected} />
          </article>

          <article className="security-policy-card missing">
            <span>MISSING APPROVED LISTENERS</span>
            <strong>{missing.length}</strong>
            <EndpointList endpoints={missing} />
          </article>
        </div>

        <p className="security-policy-note">
          {securityPolicy?.note ?? "Waiting for authoritative listener policy state."}
        </p>
      </section>

      <section className="trend-panel">
        <div className="trend-header">
          <div>
            <span>ROLLING TELEMETRY</span>
            <strong>{TELEMETRY_RANGES[telemetryRange].label}</strong>
          </div>

          <div className="trend-controls">
            {(Object.keys(TELEMETRY_RANGES) as TelemetryRange[]).map((range) => (
              <button
                type="button"
                key={range}
                className={telemetryRange === range ? "active" : ""}
                onClick={() => setTelemetryRange(range)}
              >
                {TELEMETRY_RANGES[range].label}
              </button>
            ))}
          </div>

          <small>{telemetryHistory.length} SAMPLES</small>
        </div>

        <div className="trend-grid trend-grid-five">
          <article className="trend-card">
            <div><span>CPU</span><strong>{overview ? `${overview.system.cpu.usage_percent}%` : "--"}</strong></div>
            <Sparkline values={telemetryHistory.map((sample) => sample.cpu)} />
          </article>

          <article className="trend-card">
            <div><span>GPU</span><strong>{currentGpu?.available && typeof currentGpu.usage_percent === "number" ? `${currentGpu.usage_percent}%` : "N/A"}</strong></div>
            <Sparkline values={gpuValues} />
            <small>
              {currentGpu?.available
                ? `${currentGpu.name ?? "NVIDIA GPU"} • ${currentGpu.temperature_c ?? "--"}°C • ${currentGpu.power_draw_watts ?? "--"} W / ${currentGpu.power_limit_watts ?? "--"} W`
                : "GPU TELEMETRY UNAVAILABLE"}
            </small>
          </article>

          <article className="trend-card">
            <div><span>GPU VRAM</span><strong>{currentGpu?.available && typeof currentGpu.memory_usage_percent === "number" ? `${currentGpu.memory_usage_percent}%` : "N/A"}</strong></div>
            <Sparkline values={gpuMemoryValues} />
            <small>
              {currentGpu?.available
                ? `${formatGb(currentGpu.memory_used_mb)} / ${formatGb(currentGpu.memory_total_mb)} GB`
                : "VRAM TELEMETRY UNAVAILABLE"}
            </small>
          </article>

          <article className="trend-card">
            <div><span>MEMORY</span><strong>{overview ? `${overview.system.memory.usage_percent}%` : "--"}</strong></div>
            <Sparkline values={telemetryHistory.map((sample) => sample.memory)} />
          </article>

          <article className="trend-card">
            <div><span>DISK</span><strong>{overview ? `${overview.system.disk.usage_percent}%` : "--"}</strong></div>
            <Sparkline values={telemetryHistory.map((sample) => sample.disk)} />
          </article>

          <article className="trend-card">
            <div>
              <span>AVG SERVICE LATENCY</span>
              <strong>
                {telemetryHistory.length
                  ? `${telemetryHistory[telemetryHistory.length - 1].serviceLatency.toFixed(1)} ms`
                  : "--"}
              </strong>
            </div>
            <Sparkline values={telemetryHistory.map((sample) => sample.serviceLatency)} maxValue={500} />
          </article>
        </div>
      </section>

      <footer>Dedicated system telemetry and infrastructure health</footer>
    </main>
  );
}
