import { useEffect, useState } from "react";

import {
  acknowledgeIncident,
  downloadIncidentCsv,
  getIncidentAnalytics,
  getIncidentTimeline,
  getIncidents,
  searchIncidents,
  type IncidentAnalytics,
  type IncidentEvent,
  type IncidentTimeline,
} from "../api/status";

import "../styles.css";

export default function IncidentsPage() {
  const [incidentError, setIncidentError] = useState(false);
  const [incidentLoaded, setIncidentLoaded] = useState(false);
  const [analyticsError, setAnalyticsError] = useState(false);
  const [incidents, setIncidents] = useState<IncidentEvent[]>([]);
  const [activeIncidentIds, setActiveIncidentIds] = useState<string[]>([]);
  const [acknowledgedIncidentIds, setAcknowledgedIncidentIds] = useState<string[]>([]);
  const [incidentFilter, setIncidentFilter] = useState<"all" | "opened" | "resolved">("all");
  const [incidentSeverityFilter, setIncidentSeverityFilter] = useState<"all" | "warning" | "critical" | "info">("all");
  const [selectedIncident, setSelectedIncident] = useState<IncidentTimeline | null>(null);
  const [incidentAnalytics, setIncidentAnalytics] = useState<IncidentAnalytics | null>(null);
  const [incidentSearch, setIncidentSearch] = useState("");
  const [incidentSearchBusy, setIncidentSearchBusy] = useState(false);

  useEffect(() => {
    let active = true;

    const refreshIncidents = async () => {
      try {
        const data = await getIncidents(50);
        if (!active) return;
        setIncidentLoaded(true);
        setIncidentError(false);
        setIncidents(data.incidents);
        setActiveIncidentIds(data.active);
        setAcknowledgedIncidentIds(data.acknowledged ?? []);
      } catch {
        if (active) setIncidentError(true);
      }
    };

    void refreshIncidents();
    const timer = window.setInterval(() => void refreshIncidents(), 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let active = true;

    const refreshAnalytics = async () => {
      try {
        const data = await getIncidentAnalytics();
        if (active) { setIncidentAnalytics(data); setAnalyticsError(false); }
      } catch {
        if (active) setAnalyticsError(true);
      }
    };

    void refreshAnalytics();
    const timer = window.setInterval(() => void refreshAnalytics(), 15000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function runIncidentSearch() {
    setIncidentSearchBusy(true);
    try {
      setIncidents(await searchIncidents(incidentSearch.trim()));
      setIncidentError(false);
    } catch {
      setIncidentError(true);
    } finally {
      setIncidentSearchBusy(false);
    }
  }

  async function openIncidentTimeline(incidentId: string) {
    try {
      setSelectedIncident(await getIncidentTimeline(incidentId));
    } catch {
      setSelectedIncident(null);
    }
  }

  async function acknowledgeActiveIncident(incidentId: string) {
    try {
      const result = await acknowledgeIncident(incidentId);
      if (!result.ok) return;

      const data = await getIncidents(50);
      setIncidents(data.incidents);
      setActiveIncidentIds(data.active);
      setAcknowledgedIncidentIds(data.acknowledged ?? []);
    } catch {
      // Polling will recover UI state.
    }
  }

  const activeIncidentEvents = incidents.filter(
    (incident) => incident.state === "opened" && activeIncidentIds.includes(incident.id),
  );
  const activeCriticalCount = activeIncidentEvents.filter((incident) => incident.severity === "critical").length;
  const activeWarningCount = activeIncidentEvents.filter((incident) => incident.severity === "warning").length;

  return (
    <main className="core-shell">
      <section className="header">
        <p className="eyebrow">OPERATIONAL INTELLIGENCE</p>
        <h1>Incident <span>Center</span></h1>
        <p className="subtitle">Live incidents, history, acknowledgements, search, analytics, and timelines.</p>
      </section>

      <section className="incident-analytics-panel">
        {analyticsError && <p role="alert">Incident analytics unavailable. Previous values may be out of date.</p>}
        <div className="incident-analytics-header">
          <div>
            <span>INCIDENT ANALYTICS</span>
            <strong>OPERATIONAL HISTORY</strong>
          </div>
        </div>

        <div className="incident-analytics-grid">
          <article><span>TOTAL EVENTS</span><strong>{incidentAnalytics?.total_events ?? "--"}</strong></article>
          <article><span>OPENED</span><strong>{incidentAnalytics?.opened_events ?? "--"}</strong></article>
          <article><span>RESOLVED</span><strong>{incidentAnalytics?.resolved_events ?? "--"}</strong></article>
          <article><span>ACKNOWLEDGED</span><strong>{incidentAnalytics?.acknowledged_events ?? "--"}</strong></article>
          <article>
            <span>AVG RESOLUTION</span>
            <strong>{typeof incidentAnalytics?.average_resolution_seconds === "number" ? `${incidentAnalytics.average_resolution_seconds.toFixed(1)} sec` : "--"}</strong>
          </article>
        </div>

        <div className="incident-top-list">
          <span>TOP RECURRING INCIDENTS</span>
          {incidentAnalytics?.top_incidents?.length ? (
            incidentAnalytics.top_incidents.map((item) => (
              <div key={item.incident_id}>
                <strong>{item.incident_id}</strong>
                <span>{item.occurrences} occurrence(s)</span>
              </div>
            ))
          ) : (
            <small>No recurring incidents recorded.</small>
          )}
        </div>
      </section>

      <section className="incident-panel">
        {incidentError && <p role="alert">Incident data unavailable. Previous results may be out of date.</p>}
        <div className="incident-header">
          <div>
            <span>INCIDENT MONITOR</span>
            <strong>{incidentError ? "DATA UNAVAILABLE" : !incidentLoaded ? "LOADING" : activeIncidentIds.length === 0 ? "NO ACTIVE INCIDENTS" : `${activeIncidentIds.length} ACTIVE`}</strong>
          </div>

          <div className="incident-header-actions">
            <div className="incident-counts">
              <span className="incident-count critical">CRITICAL {activeCriticalCount}</span>
              <span className="incident-count warning">WARNING {activeWarningCount}</span>
            </div>

            <div className="incident-filter-stack">
              <div className="incident-filters">
                {(["all", "opened", "resolved"] as const).map((filter) => (
                  <button
                    type="button"
                    key={filter}
                    className={incidentFilter === filter ? "active" : ""}
                    onClick={() => setIncidentFilter(filter)}
                  >
                    {filter.toUpperCase()}
                  </button>
                ))}
              </div>

              <div className="incident-filters severity-filters">
                {(["all", "warning", "critical", "info"] as const).map((severity) => (
                  <button
                    type="button"
                    key={severity}
                    className={incidentSeverityFilter === severity ? "active" : ""}
                    onClick={() => setIncidentSeverityFilter(severity)}
                  >
                    {severity.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className={activeIncidentIds.length === 0 ? "incident-indicator nominal" : "incident-indicator active"}>
              {incidentError || !incidentLoaded ? "UNKNOWN" : activeIncidentIds.length === 0 ? "CLEAR" : "ATTENTION"}
            </div>
          </div>
        </div>

        <div className="incident-search-bar">
          <input
            type="text"
            value={incidentSearch}
            onChange={(event) => setIncidentSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void runIncidentSearch();
            }}
            placeholder="Search incident history..."
          />
          <button type="button" onClick={() => void runIncidentSearch()} disabled={incidentSearchBusy}>
            {incidentSearchBusy ? "SEARCHING..." : "SEARCH"}
          </button>
          <button type="button" onClick={() => downloadIncidentCsv(incidentSearch.trim())}>EXPORT CSV</button>
        </div>

        {incidents.length === 0 ? (
          <div className="incident-empty">{incidentError ? "Unable to load incident events." : !incidentLoaded ? "Loading incidents..." : "No incident events found."}</div>
        ) : (
          <div className="incident-list">
            {[...incidents]
              .filter((incident) => {
                const stateMatches = incidentFilter === "all" || incident.state === incidentFilter;
                const severityMatches = incidentSeverityFilter === "all" || incident.severity === incidentSeverityFilter;
                return stateMatches && severityMatches;
              })
              .reverse()
              .slice(0, 12)
              .map((incident, index) => (
                <article
                  key={`${incident.id}-${incident.timestamp ?? index}`}
                  className={`incident-item incident-${incident.severity} incident-${incident.state}`}
                  onClick={() => void openIncidentTimeline(incident.id)}
                >
                  <div className="incident-item-header">
                    <strong>{incident.title}</strong>
                    <div className="incident-item-actions">
                      <span>{incident.state.toUpperCase()}</span>
                      {incident.state === "opened" &&
                        activeIncidentIds.includes(incident.id) &&
                        !acknowledgedIncidentIds.includes(incident.id) && (
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              void acknowledgeActiveIncident(incident.id);
                            }}
                          >
                            ACKNOWLEDGE
                          </button>
                        )}
                      {activeIncidentIds.includes(incident.id) && acknowledgedIncidentIds.includes(incident.id) && (
                        <span className="incident-ack-badge">ACKNOWLEDGED</span>
                      )}
                    </div>
                  </div>
                  <p>{incident.message}</p>
                  <small>
                    {incident.timestamp ? new Date(incident.timestamp).toLocaleTimeString() : "TIME N/A"}
                    {"duration_seconds" in incident && typeof incident.duration_seconds === "number"
                      ? ` • ${incident.duration_seconds.toFixed(1)} sec`
                      : ""}
                  </small>
                </article>
              ))}
          </div>
        )}

        {selectedIncident && (
          <div className="incident-detail-panel">
            <div className="incident-detail-heading">
              <div>
                <span>INCIDENT DETAIL</span>
                <strong>{selectedIncident.incident_id}</strong>
              </div>
              <button type="button" onClick={() => setSelectedIncident(null)}>CLOSE</button>
            </div>

            <div className="incident-detail-grid">
              <div><span>STATE</span><strong>{selectedIncident.active ? selectedIncident.acknowledged ? "ACKNOWLEDGED" : "ACTIVE" : "RESOLVED"}</strong></div>
              <div><span>SEVERITY</span><strong>{selectedIncident.severity?.toUpperCase() ?? "N/A"}</strong></div>
              <div>
                <span>DURATION</span>
                <strong>
                  {typeof selectedIncident.duration_seconds === "number"
                    ? `${selectedIncident.duration_seconds.toFixed(1)} sec`
                    : selectedIncident.active ? "ONGOING" : "N/A"}
                </strong>
              </div>
              <div><span>VALUE / THRESHOLD</span><strong>{selectedIncident.value ?? "N/A"} / {selectedIncident.threshold ?? "N/A"}</strong></div>
            </div>

            <div className="incident-timeline">
              {selectedIncident.events.map((event, index) => (
                <div key={`${event.state}-${event.timestamp}-${index}`} className={`timeline-event timeline-${event.state}`}>
                  <div className="timeline-dot" />
                  <div>
                    <strong>{event.state.toUpperCase()}</strong>
                    <span>{event.timestamp ? new Date(event.timestamp).toLocaleString() : "TIME N/A"}</span>
                    <p>{event.message}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
