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
  status_code?: number | null;
  reason?: string | null;
  latency_ms?: number | null;
  error?: string | null;
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
