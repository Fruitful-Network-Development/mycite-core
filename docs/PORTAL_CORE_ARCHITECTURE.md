# Portal Core Architecture

## Shared vs flavor-specific

Shared core authority lives under `portals/_shared/portal/**`:

- API composition and contracts (including shared data route registrar)
- MSS/contract compilation and foreign datum resolution
- data-engine semantics and anthology normalization
- runtime helper services (alias/embed/network contract helpers)
- typed runtime config contract (`core_services/runtime_config.py`)
- external resource isolate planning (`data_engine/external_resources/*`)

Flavor runtime files under `portals/_shared/runtime/flavors/*` are composition wrappers:

- flavor flags and behavior toggles
- flavor-only routes/extensions
- shared shell/service wiring

Canonical data route registration now lives directly in `portals/_shared/portal/api/data_workspace.py` (no flavor-level compatibility loader/indirection).

Canonical shared external-resource endpoints under `/portal/api/data/*` are shared-core owned and reusable by tools/profiles/aliases.

## Canonical shell/service surfaces

- canonical `SYSTEM` surface: `GET /portal/system`
- canonical `SYSTEM` workbench: one unified NIMM/AITAS-driven workbench for `anthology.json`, `samras-txa.json`, and `samras-msn.json`
- canonical Data Tool browser entry: `GET /portal/data` -> `/portal/tools/data_tool/home`
- canonical data service API: `/portal/api/data/*`
- canonical contract editor: `NETWORK > Contracts`
- canonical contract MSS fields:
  - `owner_selected_refs`
  - `owner_mss`
  - `counterparty_mss`

Legacy split-view SYSTEM query entrypoints have been removed from active route normalization. The canonical entry is the clean unified `/portal/system` shell.

## Shell consolidation

Shared shell assets/templates are canonicalized to one source and reused across flavors. TFF now composes shared shell template/static sources rather than carrying duplicated copies.

## Manifest boundary (`build.json`)

`build.json` is treated as bootstrap-only materialization input. Runtime semantics are served from canonical state artifacts and shared service layers, not from `build.json` at request time.

## Flavor runtime boundary

Flavor entrypoints (`portals/_shared/runtime/flavors/fnd/app.py`, `portals/_shared/runtime/flavors/tff/app.py`) compose shared services and shell behavior but do not own divergent data/MSS contracts.

Current active portal flavors (`fnd`, `tff`) render the same unified `SYSTEM` template contract: control panel on the left, one center workbench, and Details on the right.

Current shared-boundary invariants:

- shared data route registrar: `portals/_shared/portal/api/data_workspace.py`
- shared MSS implementation: `portals/_shared/portal/mss/`
- shared sandbox service ownership: `portals/_shared/portal/sandbox/`
- shared write-intent engine: `portals/_shared/portal/data_engine/write_pipeline.py`

## Compatibility and legacy shims

Current compatibility posture is explicit:

- `/portal/data` and `/portal/data/<path:tab_id>` redirect to `/portal/tools/data_tool/home`
- `/portal/tools`, `/portal/inbox`, and `/portal/peripheral` remain redirect shims into canonical shell routes
- `/portal/system` continues to normalize legacy `local_resources`, `inheritance`, `anthology`, and `resources` query values into the unified workbench
- shared data API registration is called with `include_legacy_shims=False` in both active flavors, so deprecated `/portal/api/data/tables` and `/portal/api/data/table/*` shims are intentionally disabled

## Migration notes

- TFF legacy data shim routes under `/portal/api/data/tables` and `/portal/api/data/table/*` are removed.
- Existing compatibility redirects for `/portal/tools`, `/portal/inbox`, `/portal/peripheral` remain.
- `/portal/data` is the canonical Data Tool browser entry route.
