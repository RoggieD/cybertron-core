export interface HealthResponse {
  status: string;
  service: string;
  environment: string;
  timestamp: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch("/api/health");

  if (!response.ok) {
    throw new Error(`Health request failed: ${response.status}`);
  }

  return response.json();
}
