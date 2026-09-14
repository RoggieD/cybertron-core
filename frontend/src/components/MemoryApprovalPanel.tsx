import { useCallback, useEffect, useState } from "react";

import {
  approveMemoryProposal,
  getMemoryProposalAudit,
  getMemoryProposals,
  rejectMemoryProposal,
  type MemoryProposal,
  type MemoryProposalAuditEvent,
} from "../api/memory";


function formatTimestamp(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}


export default function MemoryApprovalPanel() {
  const [proposals, setProposals] = useState<MemoryProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [audit, setAudit] = useState<
    Record<string, MemoryProposalAuditEvent[]>
  >({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await getMemoryProposals("pending");

      setProposals(result.proposals);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load memory proposals.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();

    const timer = window.setInterval(
      () => {
        void refresh();
      },
      10000,
    );

    return () => {
      window.clearInterval(timer);
    };
  }, [refresh]);

  async function toggleAudit(proposalId: string) {
    if (expandedId === proposalId) {
      setExpandedId(null);
      return;
    }

    setExpandedId(proposalId);

    if (audit[proposalId]) {
      return;
    }

    try {
      const result = await getMemoryProposalAudit(
        proposalId,
      );

      setAudit((current) => ({
        ...current,
        [proposalId]: result.events,
      }));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load proposal audit.",
      );
    }
  }

  async function decide(
    proposalId: string,
    approved: boolean,
  ) {
    setBusyId(proposalId);
    setError(null);

    try {
      if (approved) {
        await approveMemoryProposal(proposalId);
      } else {
        await rejectMemoryProposal(proposalId);
      }

      setExpandedId(null);

      setAudit((current) => {
        const next = { ...current };
        delete next[proposalId];
        return next;
      });

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Memory proposal action failed.",
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="memory-approval-panel">
      <div className="memory-approval-header">
        <div>
          <div className="memory-approval-kicker">
            MEMORY GOVERNANCE
          </div>

          <h2>
            Pending Memory Approvals
          </h2>
        </div>

        <div
          className={
            proposals.length > 0
              ? "memory-pending-badge active"
              : "memory-pending-badge"
          }
        >
          {proposals.length} PENDING
        </div>
      </div>

      {error && (
        <div className="memory-approval-error">
          {error}
        </div>
      )}

      {loading && proposals.length === 0 && (
        <div className="memory-approval-empty">
          Loading memory governance state…
        </div>
      )}

      {!loading && proposals.length === 0 && (
        <div className="memory-approval-empty">
          No memory proposals require approval.
        </div>
      )}

      <div className="memory-proposal-list">
        {proposals.map((proposal) => {
          const events =
            audit[proposal.proposal_id] ?? [];

          const isBusy =
            busyId === proposal.proposal_id;

          const isExpanded =
            expandedId === proposal.proposal_id;

          return (
            <article
              className="memory-proposal-card"
              key={proposal.proposal_id}
            >
              <div className="memory-proposal-topline">
                <span className="memory-kind-chip">
                  {proposal.kind.toUpperCase()}
                </span>

                <span className="memory-scope-chip">
                  {proposal.scope}
                </span>

                <span className="memory-proposal-status">
                  {proposal.status.toUpperCase()}
                </span>
              </div>

              <div className="memory-proposal-content">
                {proposal.content}
              </div>

              <div className="memory-proposal-grid">
                <div>
                  <span>Namespace</span>
                  <strong>
                    {proposal.namespace}
                  </strong>
                </div>

                <div>
                  <span>Proposed By</span>
                  <strong>
                    {proposal.actor_type}:
                    {proposal.actor_id}
                  </strong>
                </div>

                <div>
                  <span>Source</span>
                  <strong>
                    {proposal.source ?? "unspecified"}
                  </strong>
                </div>

                <div>
                  <span>Created</span>
                  <strong>
                    {formatTimestamp(
                      proposal.created_at,
                    )}
                  </strong>
                </div>
              </div>

              {proposal.tags.length > 0 && (
                <div className="memory-tag-row">
                  {proposal.tags.map((tag) => (
                    <span
                      className="memory-tag"
                      key={tag}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              <div className="memory-policy-reason">
                <span>POLICY</span>
                {proposal.policy_reason ??
                  "No policy reason recorded."}
              </div>

              <div className="memory-proposal-actions">
                <button
                  className="memory-action approve"
                  disabled={isBusy}
                  onClick={() => {
                    void decide(
                      proposal.proposal_id,
                      true,
                    );
                  }}
                >
                  {isBusy
                    ? "PROCESSING…"
                    : "APPROVE"}
                </button>

                <button
                  className="memory-action reject"
                  disabled={isBusy}
                  onClick={() => {
                    void decide(
                      proposal.proposal_id,
                      false,
                    );
                  }}
                >
                  REJECT
                </button>

                <button
                  className="memory-action audit"
                  disabled={isBusy}
                  onClick={() => {
                    void toggleAudit(
                      proposal.proposal_id,
                    );
                  }}
                >
                  {isExpanded
                    ? "HIDE AUDIT"
                    : "AUDIT"}
                </button>
              </div>

              {isExpanded && (
                <div className="memory-audit-trail">
                  <div className="memory-audit-title">
                    PROPOSAL LIFECYCLE
                  </div>

                  {events.length === 0 ? (
                    <div className="memory-audit-empty">
                      Loading audit trail…
                    </div>
                  ) : (
                    events.map((event) => (
                      <div
                        className="memory-audit-event"
                        key={event.id}
                      >
                        <div className="memory-audit-node" />

                        <div>
                          <strong>
                            {event.action.toUpperCase()}
                          </strong>

                          <div>
                            {event.actor_type}:
                            {event.actor_id}
                          </div>

                          <small>
                            {formatTimestamp(
                              event.timestamp,
                            )}
                          </small>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
