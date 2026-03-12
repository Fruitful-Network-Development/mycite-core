# Implementation Report: Data Tab Consolidation + NIMM Graph

Date: 2026-03-09

## Objective

- Remove `conspectus` runtime dependency.
- Consolidate Data page around anthology + NIMM interaction.
- Add anthology graph view for node/edge interaction.
- Introduce AITAS context scaffolding in NIMM state.
- Add daemon-port scaffolding for external datum reference indirection.

## Implemented

Portal scope applied:

- `mycite-le_fnd`
- `mycite-le_tff`
- `mycite-le_cvcc`

1. Anthology-only storage model
- Removed `conspectus` from portal `TABLE_SPECS` and storage branches.
- Removed `conspectus` read/write conversion methods.
- Updated storage backend documentation/comments accordingly.

2. VG0 selection references in anthology
- Added VG0 sync routine that normalizes:
- `pairs[*].magnitude = "0"`
- row-level `magnitude = JSON list of selection references`
- Updated anthology table payload fields to:
- `selection_references`
- `selection_count`

3. Time-series decoupled from `conspectus`
- `time_series_state()` now computes indexed event refs directly from anthology event rows.
- Removed `conspectus` loading for event index state.

4. NIMM state model: AITAS
- Added `aitas_context` to persisted state:
- `attention`, `intention`, `temporal`, `archetype`, `spacial`
- Directive handling (`nav`, `inv`, `med`, `man`) now updates AITAS context from focus and directive args.

5. Anthology graph endpoint
- Added `anthology_graph_view()` workspace payload:
- `nodes`, `edges`, `layers`, `stats`
- Added API route:
- `GET /portal/api/data/anthology/graph`

6. Daemon-port scaffolding
- Added workspace methods:
- `daemon_port_catalog()`
- `daemon_port_resolve()`
- Added API routes:
- `GET /portal/api/data/daemon/ports`
- `POST /portal/api/data/daemon/resolve`

7. Data UI consolidation (FND/TFF/CVCC)
- Removed all UI copy and logic references to `conspectus`.
- Added anthology graph panel on Data page.
- Added graph interactions:
- single-click node => NIMM `inv;summary`
- double-click node => open datum profile modal
- Data page now opens NIMM overlay by default for anthology/advanced tabs.
- NIMM summary now includes AITAS context and daemon-port count.

## Files changed

- `portals/mycite-le_fnd/data/storage_json.py`
- `portals/mycite-le_fnd/data/engine/nimm/state.py`
- `portals/mycite-le_fnd/data/engine/workspace.py`
- `portals/mycite-le_fnd/portal/api/data_workspace.py`
- `portals/mycite-le_fnd/portal/ui/templates/tools/data_tool_home.html`
- `portals/mycite-le_fnd/portal/ui/static/tools/data_tool.js`
- `portals/mycite-le_tff/data/storage_json.py`
- `portals/mycite-le_tff/data/engine/nimm/state.py`
- `portals/mycite-le_tff/data/engine/workspace.py`
- `portals/mycite-le_tff/portal/api/data_workspace.py`
- `portals/mycite-le_tff/portal/ui/templates/tools/data_tool_home.html`
- `portals/mycite-le_tff/portal/ui/static/tools/data_tool.js`
- `portals/mycite-le_cvcc/data/storage_json.py`
- `portals/mycite-le_cvcc/data/engine/nimm/state.py`
- `portals/mycite-le_cvcc/data/engine/workspace.py`
- `portals/mycite-le_cvcc/portal/api/data_workspace.py`
- `portals/mycite-le_cvcc/portal/ui/templates/tools/data_tool_home.html`
- `portals/mycite-le_cvcc/portal/ui/static/tools/data_tool.js`
- `docs/DATA_TOOL.md`
- `docs/IMPLEMENTATION_REPORT_2026-03-09_DATA_TAB_NIMM.md`

## Verification performed

- Python syntax compile:
- `python3 -m py_compile portals/mycite-le_fnd/data/storage_json.py`
- `python3 -m py_compile portals/mycite-le_fnd/data/engine/nimm/state.py`
- `python3 -m py_compile portals/mycite-le_fnd/data/engine/workspace.py`
- `python3 -m py_compile portals/mycite-le_fnd/portal/api/data_workspace.py`
- `python3 -m py_compile portals/mycite-le_tff/data/storage_json.py`
- `python3 -m py_compile portals/mycite-le_tff/data/engine/nimm/state.py`
- `python3 -m py_compile portals/mycite-le_tff/data/engine/workspace.py`
- `python3 -m py_compile portals/mycite-le_tff/portal/api/data_workspace.py`
- `python3 -m py_compile portals/mycite-le_cvcc/data/storage_json.py`
- `python3 -m py_compile portals/mycite-le_cvcc/data/engine/nimm/state.py`
- `python3 -m py_compile portals/mycite-le_cvcc/data/engine/workspace.py`
- `python3 -m py_compile portals/mycite-le_cvcc/portal/api/data_workspace.py`

Result: pass.

## Known follow-up

- Roll this exact consolidation pass into remaining non-active portals (`mycite-ne_mt`, `mycite-ne_mw`) if you want full repo-wide parity.
- Remove legacy conspectus artifacts from active portal instances (completed in follow-up alignment pass).
- Expand AITAS-driven mediation behavior once anthology data-type standards are finalized.

## Addendum: Anthology Consolidation (2026-03-09)

- Consolidated SAMRAS instance JSON contents into FND anthology (`layer=3`, `value_group=1`) with parent references:
  - `2-1-48` for `...1-1-4.json`
  - `2-1-47` for `...1-1-5.json`
- Corrected partially seeded rows to respect those parent datum mappings.
- Anthology now includes all entries from both SAMRAS tables in `3-1-*`.
- `anthology.json` was normalized and written in deterministic order:
  - sort: `layer`, then `value_group`, then `iteration`.
- Storage adapters now sort anthology rows on both load and persist paths so reads/writes keep this ordering contract.
