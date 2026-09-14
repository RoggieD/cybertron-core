export type SecurityPolicyEvaluation = {
  hostname?: string;
  mode: string;
  approved_configured: boolean;
  approved_public_listener_count?: number;
  current_public_listener_count?: number;
  approved_public_listener_endpoints?: string[];
  unexpected_public_listener_endpoints: string[];
  missing_approved_public_listener_endpoints: string[];
  note?: string;
};

export async function getSecurityPolicyEvaluation(
  hostname: string,
): Promise<SecurityPolicyEvaluation> {
  const host = window.location.hostname;
  const response = await fetch(
    `http://${host}:8000/api/security/policy/${encodeURIComponent(hostname)}/evaluate`,
  );

  if (!response.ok) {
    throw new Error(`Security policy API returned ${response.status}`);
  }

  return response.json();
}
