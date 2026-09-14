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
  const host = window.location.hostname;

  const response = await fetch(
    `http://${host}:8000/api/status/overview`
  );

  if (!response.ok) {
    throw new Error(
      `Status API returned ${response.status}`
    );
  }

  return response.json();
}

export async function getServiceStatus(): Promise<ServiceHealthResponse> {
  const host = window.location.hostname;

  const response = await fetch(
    `http://${host}:8000/api/status/services`
  );

  if (!response.ok) {
    throw new Error(
      `Service status API returned ${response.status}`
    );
  }

  return response.json();
}

export type TelemetryHistorySample = {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
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
  const host = window.location.hostname;

  const response = await fetch(
    `http://${host}:8000/api/status/history?limit=${limit}`
  );

  if (!response.ok) {
    throw new Error(
      `Telemetry history API returned ${response.status}`
    );
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
};

export type IncidentResponse = {
  active: string[];
  count: number;
  incidents: IncidentEvent[];
};

export async function getIncidents(
  limit = 20
): Promise<IncidentResponse> {
  const host = window.location.hostname;

  const response = await fetch(
    `http://${host}:8000/api/status/incidents?limit=${limit}`
  );

  if (!response.ok) {
    throw new Error(
      `Incident API returned ${response.status}`
    );
  }

  return response.json();
}
