export type MemoryProposalStatus =
  | "pending"
  | "committed"
  | "rejected";

export interface MemoryProposal {
  proposal_id: string;
  status: MemoryProposalStatus;
  actor_type: string;
  actor_id: string;
  namespace: string;
  scope: string;
  kind: string;
  content: string;
  tags: string[];
  source: string | null;
  policy_decision_id: string | null;
  policy_reason: string | null;
  memory_id: string | null;
  created_at: string;
  updated_at: string;
  decided_by_type: string | null;
  decided_by_id: string | null;
  decided_at: string | null;
}

export interface MemoryProposalList {
  status_filter: string | null;
  count: number;
  proposals: MemoryProposal[];
}

export interface MemoryProposalAuditEvent {
  id: number;
  proposal_id: string;
  action: string;
  actor_type: string;
  actor_id: string;
  detail: Record<string, unknown>;
  timestamp: string;
}

export interface MemoryProposalAudit {
  proposal_id: string;
  count: number;
  events: MemoryProposalAuditEvent[];
}

export async function getMemoryProposals(
  status = "pending",
): Promise<MemoryProposalList> {
  const response = await fetch(
    `/api/memory/proposals?status=${encodeURIComponent(status)}`,
  );

  if (!response.ok) {
    throw new Error(
      `Memory proposals request failed: ${response.status}`,
    );
  }

  return response.json();
}

export async function getMemoryProposalAudit(
  proposalId: string,
): Promise<MemoryProposalAudit> {
  const response = await fetch(
    `/api/memory/proposals/${encodeURIComponent(proposalId)}/audit`,
  );

  if (!response.ok) {
    throw new Error(
      `Memory audit request failed: ${response.status}`,
    );
  }

  return response.json();
}

export async function approveMemoryProposal(
  proposalId: string,
): Promise<void> {
  const response = await fetch(
    `/api/memory/proposals/${encodeURIComponent(proposalId)}/approve`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error(
      `Memory approval failed: ${response.status}`,
    );
  }
}

export async function rejectMemoryProposal(
  proposalId: string,
): Promise<void> {
  const response = await fetch(
    `/api/memory/proposals/${encodeURIComponent(proposalId)}/reject`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    throw new Error(
      `Memory rejection failed: ${response.status}`,
    );
  }
}
