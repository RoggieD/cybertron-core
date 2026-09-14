export type StatusOverview = {
  system: {
    hostname: string;
    platform: string;
    cpu: {
      logical_cores: number;
      physical_cores: number;
      usage_percent: number;
    };
    memory: {
      usage_percent: number;
    };
    disk: {
      usage_percent: number;
    };
    gpu: {
      available: boolean;
      name?: string | null;
      usage_percent?: number | null;
      memory_used_mb?: number | null;
      memory_total_mb?: number | null;
      memory_usage_percent?: number | null;
      temperature_c?: number | null;
      power_draw_watts?: number | null;
      power_limit_watts?: number | null;
      power_usage_percent?: number | null;
    };
    uptime_seconds: number;
  };

  docker: {
    available: boolean;
    total: number;
    running: number;
  };

  services: {
    total: number;
    reachable: number;
    unreachable: number;
  };

  network: {
    listeners: number;
  };
};

export type ServiceHealthItem = {
  name: string;
  scope: string;
  reachable: boolean;
  target?: string | null;
  target_configured?: string | null;
  status_code?: number | null;
  reason?: string | null;
  latency_ms?: number | null;
  error?: string | null;

  container?: string | null;
  container_port?: number | null;
  protocol?: string | null;
  health_path?: string | null;
  image?: string | null;
  container_status?: string | null;
  container_health?: string | null;
  networks?: string[];
};

export type ServiceHealthResponse = {
  total: number;
  reachable: number;
  unreachable: number;
  services: ServiceHealthItem[];
};

export async function getStatusOverview(): Promise<StatusOverview> {
  const response = await fetch("/api/status/overview");

  if (!response.ok) {
    throw new Error(`Status API returned ${response.status}`);
  }

  return response.json();
}

export async function getServiceStatus(): Promise<ServiceHealthResponse> {
  const response = await fetch("/api/status/services");

  if (!response.ok) {
    throw new Error(`Service status API returned ${response.status}`);
  }

  return response.json();
}

export type TelemetryHistorySample = {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  gpu_percent?: number | null;
  gpu_memory_percent?: number | null;
  gpu_power_watts?: number | null;
  docker_running: number;
  docker_total: number;
  services_reachable: number;
  services_total: number;
  listeners: number;
  service_latency_ms: number;
};

export type TelemetryHistoryResponse = {
  count: number;
  samples: TelemetryHistorySample[];
};

export async function getTelemetryHistory(
  limit = 240
): Promise<TelemetryHistoryResponse> {
  const response = await fetch(`/api/status/history?limit=${limit}`);

  if (!response.ok) {
    throw new Error(`Telemetry history API returned ${response.status}`);
  }

  return response.json();
}

export type IncidentEvent = {
  id: string;
  severity: string;
  title: string;
  message: string;
  state: string;
  timestamp?: string;
  value?: number | null;
  threshold?: number | null;
  duration_seconds?: number | null;
};

export type IncidentResponse = {
  active: string[];
  acknowledged: string[];
  count: number;
  incidents: IncidentEvent[];
};

export async function getIncidents(
  limit = 20
): Promise<IncidentResponse> {
  const response = await fetch(`/api/status/incidents?limit=${limit}`);

  if (!response.ok) {
    throw new Error(`Incident API returned ${response.status}`);
  }

  return response.json();
}

export async function acknowledgeIncident(
  incidentId: string
): Promise<{
  ok: boolean;
  already_acknowledged?: boolean;
  reason?: string;
  incident_id: string;
}> {
  const response = await fetch(
    `/api/status/incidents/${encodeURIComponent(incidentId)}/acknowledge`,
    {
      method: "POST"
    }
  );

  if (!response.ok) {
    throw new Error(`Incident acknowledgment returned ${response.status}`);
  }

  return response.json();
}

export type IncidentTimeline = {
  incident_id: string;
  found: boolean;
  active: boolean;
  acknowledged: boolean;
  opened_at?: string | null;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  duration_seconds?: number | null;
  severity?: string | null;
  value?: number | null;
  threshold?: number | null;
  events: IncidentEvent[];
};

export async function getIncidentTimeline(
  incidentId: string
): Promise<IncidentTimeline> {
  const response = await fetch(
    `/api/status/incidents/${encodeURIComponent(incidentId)}`
  );

  if (!response.ok) {
    throw new Error(`Incident timeline returned ${response.status}`);
  }

  return response.json();
}

export async function searchIncidents(
  query: string
): Promise<IncidentEvent[]> {
  const response = await fetch(
    `/api/status/incidents/search?q=${encodeURIComponent(query)}&limit=200`
  );

  if (!response.ok) {
    throw new Error(`Incident search returned ${response.status}`);
  }

  const data = await response.json();

  return data.incidents;
}

export function downloadIncidentCsv(
  query = ""
): void {
  window.location.href =
    `/api/status/incidents/export?q=${encodeURIComponent(query)}`;
}

export type IncidentAnalytics = {
  total_events: number;
  opened_events: number;
  resolved_events: number;
  acknowledged_events: number;
  critical_opened: number;
  warning_opened: number;
  average_resolution_seconds: number;
  resolved_samples: number;
  top_incidents: {
    incident_id: string;
    occurrences: number;
  }[];
};

export async function getIncidentAnalytics(): Promise<IncidentAnalytics> {
  const response = await fetch("/api/status/incidents/analytics");

  if (!response.ok) {
    throw new Error(`Incident analytics returned ${response.status}`);
  }

  return response.json();
}
