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

- canonical Data Tool browser entry: `GET /portal/data` -> `/portal/tools/data_tool/home`
- canonical data service API: `/portal/api/data/*`
- canonical contract editor: `NETWORK > Contracts`
- canonical contract MSS fields:
  - `owner_selected_refs`
  - `owner_mss`
  - `counterparty_mss`

## Shell consolidation

Shared shell assets/templates are canonicalized to one source and reused across flavors. TFF now composes shared shell template/static sources rather than carrying duplicated copies.

## Manifest boundary (`build.json`)

`build.json` is treated as bootstrap-only materialization input. Runtime semantics are served from canonical state artifacts and shared service layers, not from `build.json` at request time.

## Migration notes

- TFF legacy data shim routes under `/portal/api/data/tables` and `/portal/api/data/table/*` are removed.
- Existing compatibility redirects for `/portal/tools`, `/portal/inbox`, `/portal/peripheral` remain.
- `/portal/data` is the canonical Data Tool browser entry route.
