import { useEffect, useState } from "react";

import {
  getServiceStatus,
  type ServiceHealthItem,
} from "../api/status";

import "../styles.css";

export default function ServicesPage() {
  const [loaded, setLoaded] = useState(false);
  const [services, setServices] = useState<ServiceHealthItem[]>([]);
  const [selectedService, setSelectedService] =
    useState<ServiceHealthItem | null>(null);
  const [manualCheckBusy, setManualCheckBusy] = useState(false);
  const [lastManualCheck, setLastManualCheck] = useState<Date | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      try {
        const serviceData = await getServiceStatus();
        if (!active) return;
        setLoaded(true);
        setServices(serviceData.services);
        setError(false);

        setSelectedService((current) => {
          if (!current) return null;

          return (
            serviceData.services.find(
              (service) => service.name === current.name,
            ) ?? current
          );
        });
      } catch {
        if (active) setError(true);
      }
    };

    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  async function checkSelectedService() {
    if (!selectedService || manualCheckBusy) return;

    setManualCheckBusy(true);

    try {
      const serviceData = await getServiceStatus();
      setServices(serviceData.services);
      setLoaded(true);

      const refreshed =
        serviceData.services.find(
          (service) => service.name === selectedService.name,
        ) ?? selectedService;

      setSelectedService(refreshed);
      setLastManualCheck(new Date());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setManualCheckBusy(false);
    }
  }

  return (
    <main className="core-shell">
      <section className="header">
        <p className="eyebrow">CYBERTRON SERVICES</p>
        <h1>
          Service <span>Matrix</span>
        </h1>
        <p className="subtitle">
          Reachability, container state, latency, and health diagnostics
        </p>
      </section>

      <section className="service-health-panel">
        <p className="subtitle">Reachability is checked from the backend. Select a service for its target, response and any check error.</p>
        {error && <p role="alert">Service checks are unavailable. Displayed results may be out of date.</p>}
        <div className="service-health-header">
          <div>
            <span>SERVICE MATRIX</span>
            <strong>
              {error
                ? "LINK ERROR"
                : loaded
                  ? `${services.filter(service => service.reachable).length}/${services.length} REACHABLE`
                  : "ACQUIRING..."}
            </strong>
          </div>
        </div>

        <div className="service-card-grid">
          {services.map((service) => (
            <button
              type="button"
              key={service.name}
              className={`service-card ${
                service.reachable ? "service-up" : "service-down"
              } ${
                selectedService?.name === service.name ? "selected" : ""
              }`}
              onClick={() => setSelectedService(service)}
            >
              <span>{service.name}</span>
              <strong>{service.reachable ? "REACHABLE" : "CHECK FAILED"}</strong>
              <small>
                {service.scope.toUpperCase()}
                {typeof service.latency_ms === "number"
                  ? ` • ${service.latency_ms} ms`
                  : ""}
              </small>
            </button>
          ))}
        </div>

        {selectedService && (
          <div className="service-detail">
            <div className="service-detail-heading">
              <div>
                <span>SELECTED SERVICE</span>
                <strong>{selectedService.name}</strong>
              </div>

              <div className="service-detail-actions">
                <button
                  type="button"
                  onClick={() => void checkSelectedService()}
                  disabled={manualCheckBusy}
                >
                  {manualCheckBusy ? "CHECKING..." : "CHECK NOW"}
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedService(null)}
                >
                  CLOSE
                </button>
              </div>
            </div>

            <div className="service-detail-grid">
              <div>
                <span>STATE</span>
                <strong
                  className={selectedService.reachable ? "online" : "warning"}
                >
                  {selectedService.reachable ? "REACHABLE" : "CHECK FAILED"}
                </strong>
              </div>

              <div>
                <span>SCOPE</span>
                <strong>{selectedService.scope.toUpperCase()}</strong>
              </div>

              <div>
                <span>HTTP</span>
                <strong>{selectedService.status_code ?? "N/A"}</strong>
              </div>

              <div>
                <span>LATENCY</span>
                <strong>
                  {typeof selectedService.latency_ms === "number"
                    ? `${selectedService.latency_ms} ms`
                    : "N/A"}
                </strong>
              </div>
            </div>

            <div className="service-target">
              <span>TARGET</span>
              <code>{selectedService.target ?? "Not reported"}</code>
            </div>

            {selectedService.scope === "docker" && (
              <div className="service-drilldown-grid">
                <div>
                  <span>CONTAINER</span>
                  <strong>{selectedService.container ?? "N/A"}</strong>
                </div>

                <div>
                  <span>IMAGE</span>
                  <strong>{selectedService.image ?? "N/A"}</strong>
                </div>

                <div>
                  <span>CONTAINER STATE</span>
                  <strong>{selectedService.container_status ?? "N/A"}</strong>
                </div>

                <div>
                  <span>CONTAINER HEALTH</span>
                  <strong>{selectedService.container_health ?? "N/A"}</strong>
                </div>

                <div>
                  <span>INTERNAL PORT</span>
                  <strong>{selectedService.container_port ?? "N/A"}</strong>
                </div>

                <div>
                  <span>HEALTH PATH</span>
                  <strong>{selectedService.health_path ?? "/"}</strong>
                </div>
              </div>
            )}

            {selectedService.scope === "docker" &&
              selectedService.networks &&
              selectedService.networks.length > 0 && (
                <div className="service-networks">
                  <span>NETWORKS</span>
                  <strong>{selectedService.networks.join(", ")}</strong>
                </div>
              )}

            <div className="service-last-check">
              <span>LAST MANUAL CHECK</span>
              <strong>
                {lastManualCheck
                  ? lastManualCheck.toLocaleTimeString()
                  : "NOT RUN"}
              </strong>
            </div>

            {selectedService.error && (
              <div className="service-error">{selectedService.error}</div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
