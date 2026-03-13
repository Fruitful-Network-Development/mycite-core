# Canonical Data Engine

## Canonical source

Portal data runtime is file-backed.

- canonical anthology: `data/anthology.json`
- canonical example anthology currently under active development:
  - `/srv/compose/portals/state/example_portal/data/anthology.json`

Repo `build.json` files may record anthology metadata/checksum, but anthology content remains state-owned in this phase and is never overwritten by materialization.

## Workbench contract

The Data Tool is a core SYSTEM workbench surface, not an optional packaged tool.

Workbench layouts:

- `table` (default)
- `linear`
- `radial`

Graph behavior:

- panning/scrolling is done through the graph surface/viewport
- zoom is controlled by the explicit `+` / `-` UI controls
- node selection opens datum editing/detail in the right inspector column

## Datum and mediation model

Canonical datum ordering remains:

1. layer
2. value group
3. iteration

Shared anthology normalization:

- `portals/_shared/portal/data_engine/anthology_normalization.py`

Shared mediation registry:

- `portals/_shared/portal/mediation/registry.py`

Compatibility aliases remain accepted for legacy magnitudes, but canonical behavior is driven through the shared mediation registry.

## Reference model

Within portal/runtime metadata, datum references should converge on:

- `<msn_id>.<datum>`

Compatibility policy:

- local refs remain readable
- legacy hyphen-qualified refs remain readable
- new network-facing writes should use dot-qualified refs

## Daemon ownership

Daemon resolution remains owned by the Data Engine.

Network-facing daemon endpoints are wrappers over Data Engine resolution and should not duplicate graph/token logic.

Canonical Data Engine daemon routes:

- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`
- `POST /portal/api/data/daemon/resolve_tokens`

## Storage boundary

There is no portal application database in this runtime. Portal data, hosted metadata, request logs, progeny profiles, and workbench state remain JSON/ndjson/file backed.
