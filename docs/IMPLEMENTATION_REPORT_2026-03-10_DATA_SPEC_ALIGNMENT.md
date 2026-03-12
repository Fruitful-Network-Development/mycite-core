# Implementation Report: Data Spec Alignment (Anthology + NIMM)

Date: 2026-03-10

## Scope reviewed

Source request reviewed: Data tab refactor requirements covering:

- removal of `conspectus` runtime usage
- VG0 behavior embedded in anthology magnitude payloads
- single Data view focused on anthology + NIMM interaction
- graph-first interaction with editable anthology datum flow
- AITAS context model in NIMM state
- daemon/port scaffolding for external datum-address indirection
- documentation and implementation reporting

## Implementation status matrix

1. `conspectus` removed from runtime data model: **implemented**
- storage adapters only expose anthology + SAMRAS runtime tables
- anthology/VG0 now holds selection references directly
- legacy `demo-conspectus.json` artifacts removed from active portal instances

2. VG0 iterations hold list references in magnitude payload: **implemented**
- VG0 normalization sync enforces selection references in row magnitude JSON
- write/append/update/delete operations trigger VG0 consistency sync

3. Data tab consolidated to one anthology-centric view: **implemented**
- canonical route is now `GET /portal/home?tab=data`
- legacy `/portal/data*` routes redirect to Home Data tab
- no second-level Data tab navigation in active flow

4. Data opens as NIMM interactive workspace with graph + edit loop: **implemented**
- Data tab now includes anthology node/edge graph panel
- graph interactions:
  - single click: focus/investigate summary via NIMM
  - double click: open datum profile editor modal
- NIMM advanced overlay opens by default on Data load

5. Duplicate layered blocks in Data view: **resolved**
- graph now renders as one canvas with lane guides (not duplicated accordion layer stacks)
- anthology table retains one canonical grouped layer/value-group editor

6. AITAS context model in NIMM state: **implemented**
- state facets present: `attention`, `intention`, `temporal`, `archetype`, `spacial`
- directive handlers (`nav/inv/med/man`) merge/update AITAS context

7. Daemon port/secure reference scaffolding: **implemented (scaffold level)**
- catalog + resolve behavior implemented in workspace
- API endpoints exposed:
  - `GET /portal/api/data/daemon/ports`
  - `POST /portal/api/data/daemon/resolve`
- merges static port context with directive context (AITAS-aware)

8. Advanced mediation facets beyond current anthology type standards: **partially implementable**
- implemented: core state scaffolding + directive channels + abstraction path view support
- pending by design: richer temporal/spacial/archetype operations requiring finalized ontology/type standards

9. Iteration compaction + reference remap: **implemented**
- after anthology mutation flows, identifiers are compacted by `(layer, value_group)` to keep iterations contiguous from `1`
- row references are remapped to new identifiers when compaction shifts positions
- qualified references and directive row references are remapped in the same normalization pass

## Files updated in this alignment pass

- `portals/mycite-le_fnd/portal/ui/templates/tools/partials/data_tool_shell.html`
- `portals/mycite-le_fnd/portal/ui/static/tools/data_tool.js`
- `portals/mycite-le_fnd/portal/ui/static/portal.css`
- `portals/mycite-le_fnd/app.py`
- `portals/mycite-le_tff/app.py`
- `portals/mycite-le_cvcc/app.py`
- synchronized from FND to TFF/CVCC:
  - `portal/ui/templates/tools/partials/data_tool_shell.html`
  - `portal/ui/static/tools/data_tool.js`
  - `portal/ui/static/portal.css`
- documentation:
  - `docs/DATA_TOOL.md`
  - `docs/TIME_SERIES_ABSTRACTION.md`
  - `docs/IMPLEMENTATION_REPORT_2026-03-10_DATA_SPEC_ALIGNMENT.md`

## Verification summary

- all three active portals rebuilt and restarted (`fnd_portal`, `tff_portal`, `cvcc_portal`)
- `/healthz` returns `200` for active portal ports
- Home Data HTML includes:
  - graph container (`#dtAnthologyGraph`)
  - single anthology layer container (`#dtAnthologyLayers`)
  - NIMM overlay auto-open flag enabled (`data-open-nimm="1"`)
- legacy Data route compatibility:
  - `/portal/data` redirects to `/portal/home?tab=data`

## Known non-goals in this pass

- automatic ontology/type inference for full facet-aware mediation logic
- daemon execution sandboxing/policy model beyond current scaffold
- removal of legacy placeholder files that are intentionally retained for migration safety
