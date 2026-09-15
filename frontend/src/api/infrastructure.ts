export type InfrastructureNode = {
  id: string; kind: "host" | "engine" | "container" | "service";
  label: string; state: string; source: string; observed_at: string; trace_id: string;
  details: Record<string, unknown>;
};
export type InfrastructureSnapshot = {
  trace_id: string; started_at: string; finished_at: string; omitted: number;
  nodes: InfrastructureNode[];
  edges: {source: string; target: string; relation: string; basis: string}[];
  sources: {tool: string; started_at: string; finished_at: string; error: string | null}[];
};

export async function getInfrastructure(signal: AbortSignal): Promise<InfrastructureSnapshot> {
  const response = await fetch("/api/status/infrastructure", {signal});
  if (!response.ok) throw new Error(`Infrastructure check failed (${response.status})`);
  return response.json();
}

export function filterInfrastructure(snapshot: InfrastructureSnapshot, query: string, kind: string) {
  const term = query.trim().toLowerCase();
  const nodes = snapshot.nodes.filter(node => (kind === "all" || node.kind === kind) &&
    `${node.label} ${node.state} ${JSON.stringify(node.details)}`.toLowerCase().includes(term));
  const ids = new Set(nodes.map(node => node.id));
  return {nodes, edges: snapshot.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target))};
}
