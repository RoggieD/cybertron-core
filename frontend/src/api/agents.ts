export type AgentSummary = {
  id: string;
  name: string;
  description: string;
};

export type AgentList = {
  count: number;
  agents: AgentSummary[];
  default_mode: "auto";
};

export async function getAgents(): Promise<AgentList> {
  const response = await fetch("/api/agents");
  if (!response.ok) {
    throw new Error(`Agent registry returned ${response.status}`);
  }
  return response.json();
}
