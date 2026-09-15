# Infrastructure explorer

Open **Systems** to collect a read-only infrastructure snapshot. Rotate and zoom
the 3D view, click a node to focus it, or select an entity in the keyboard-accessible
list. Search matches names, states and detail fields; type filters hide unrelated
entities and edges. Reset View resets the camera and selection. The list and
inspector remain available when WebGL is unavailable.

## Evidence and relationships

`GET /api/status/infrastructure` calls the existing registered `system.snapshot`,
`docker.inventory` and `service.status` tools. Each source has start/end timestamps
and independent error reporting. A failed source does not erase successful sources.
The inspector shows a node's tool, observation time, detail fields and relationships.

- Host **QUERIES** Docker endpoint: Docker CLI endpoint placement is not inferred.
- Docker endpoint **INVENTORIES** container: returned by the actual inventory.
- Host **PROBES** service: checked from the backend, not proof of where it runs.
- Container **SERVICE_TARGET** service: exact configured container-name match and
  a returned container state from service inspection; no fuzzy matching.

Reachable means the probe received a response, not that the application is healthy.
Running without explicit Docker health evidence is not labeled healthy. No cloud,
remote-host or container deployment relationships are guessed.

## Snapshot lifecycle and trace

Initial page entry and Refresh Snapshot perform collection. This explorer does not
poll continuously. After one minute the UI labels the snapshot older; failed refreshes
retain previous results with a warning. A successful refresh replaces the snapshot,
including removal of entities no longer observed. Source collection has a 25-second
await timeout; subprocess limits in existing tools still apply.

Snapshots contain at most 200 container and 100 service nodes, plus host and endpoint;
the omission count is visible. No dangling edges are returned. Stable identities use
container IDs and configured service identities rather than array order.

The trace link opens the persisted `infrastructure.snapshot` event, including the
bounded graph projection and source timestamps. This is historical inspection
evidence, not an ongoing assertion of current state. These UI inspections are saved
directly to the existing trace store and do not interrupt chat event animation or
create conversational episodes. Trace IDs are references, not authorization tokens;
the endpoint inherits the existing local deployment access model.

## Scope of this milestone

This is the first infrastructure explorer, not yet the document/memory relationship
graph, remote-host discovery, automatic dependency discovery or active-path replay.
The Processing page continues to show request execution separately. Existing Systems
telemetry remains below the explorer. No new write operations or dependencies were added.

## Live validation

Restart the backend after pulling and rebuild/restart the frontend. Open Systems:

1. Confirm the host and observed Docker/services appear, or explicit source errors.
2. Select a container; check its ID, image, state, tool and timestamp.
3. Search for a service and inspect its target and any probe error.
4. Open the snapshot trace and compare the selected entity's recorded details.
5. Refresh; confirm a new trace/time and that filters still work.

An empty container inventory is distinct from a failed Docker inspection. The
automated tests use fixtures; they do not establish live state on GM-AI01.
