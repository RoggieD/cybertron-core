# Console UI repairs

The shared navigation uses the supplied CyberTron logo as a home button. The
dashboard title is CyberTron Orchestration & Reasoning Engine. The large central
CSS reactor has been removed; its real execution and telemetry states remain in
a compact status row, and the separate voice reactor remains functional.

## Incidents

Literal analytics, search and CSV export routes precede the incident-ID route.
Previously those requests returned incident-detail objects, causing analytics
rendering to fail and unmount the entire console. A page error boundary now keeps
navigation available if a secondary page fails. Unavailable incident data is
reported explicitly rather than implying that no incidents exist.

## Service Matrix

The count and cards now come from one service-check response. Labels describe
reachability, not overall application health. Failed refreshes mark previous
results as potentially stale. Select a card to inspect the backend's actual
target and error.

The frontend probe defaults to HTTPS to match the Vite development server:

```dotenv
CYBERTRON_FRONTEND_HEALTH_URL=https://localhost:5173
CYBERTRON_FRONTEND_HEALTH_CA_FILE=certs/cybertron-core.pem
```

The configured local certificate is an explicit trust anchor for this probe;
TLS and hostname verification stay enabled. If the certificate does not include
localhost, configure a URL whose hostname is covered by the certificate. For an
HTTP deployment, configure its HTTP URL. These are backend settings; restart the
backend after changing them. No certificate or private key is committed.

## Validation

Regression tests cover literal incident routes, CSV export with additional event
fields, incident-ID lookup, configured service targets and certificate validation
failures. Run the backend suite, frontend tests and production build.

After updating, restart the backend and rebuild/restart the frontend as appropriate
for the deployment. Check Incidents, search/export, the frontend service's detailed
probe result, the new dashboard title and the logo's return-to-dashboard action.
