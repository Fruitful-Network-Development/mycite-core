# CTS-GIS SAMRAS History Audit 2026-04-17

## Scope

This audit traces the structural authority for SAMRAS, the later CTS-GIS UI drift toward row-driven hierarchy rendering, and the current live data defects affecting node addressing.

## Historical Lineage

### V1 structural authority

- `e298098` (`Cut Over Pass 3`, 2026-04-10) introduced the real SAMRAS engine in the legacy shared portal SAMRAS path.
- The authoritative V1 modules were:
  - `codec.py`
  - `structure.py`
  - `validation.py`
  - `mutation.py`
  - `workspace_adapter.py`
- Those modules established the canonical rules still used here:
  - breadth-first child-count decode
  - derived node addresses
  - contiguous roots and children
  - fail-closed validation and round-trip enforcement

### V1 documentation authority

- `b723edc` (`Cut over`, 2026-04-11) added legacy wiki documentation that matched the V1 code:
  - `docs/wiki/legacy/samras/README.md`
  - `docs/wiki/legacy/samras/structural-model.md`
  - `docs/wiki/legacy/samras/validity-and-mutation.md`
  - `docs/wiki/legacy/samras/engine-ui-boundary.md`
  - `docs/wiki/legacy/tools/time-address-schema.md`
- Those docs explicitly said:
  - SAMRAS stores child counts, not stored addresses
  - addresses are derived breadth-first
  - UI edits addresses, while engine rebuilds canonical magnitude
  - raw magnitudes are not the normal UI authoring path

### V2 drift

- `eddc123` (`v2.5.3 CTS-GIS Legacy maps Removal Alignment Plan`, 2026-04-16) introduced the current live administrative source file:
  - `deployed/fnd/data/sandbox/cts-gis/sources/sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json`
- `79bd733` (`CTS-GIS Tool Language and Interface-Body Unification`, 2026-04-15) moved CTS-GIS into a unified interface-body contract, but the navigation model already depended on explicit row extraction in `portal_cts_gis_runtime.py`.
- `65d8f55` (`CTS-GIS Scaffold Reset and Ordered-Hierarchy Rebuild`, 2026-04-17) doubled down on row-derived hierarchy rendering through ordered hierarchy payloads.
- `ad72563` (`CTS-GIS Staged Diktataograph Reset`, 2026-04-17) replaced that ordered view with staged lineage blocks, but the structure source still came from extracted administrative node rows rather than the `msn-SAMRAS` magnitude.
- During this same period, `MyCiteV2/packages/core/structures/samras/` remained an inert placeholder, so V2 had no active in-repo structural authority even though V1 already defined one.

## Current Runtime Files

The CTS-GIS remediation in this pass touches:

- `MyCiteV2/packages/core/structures/samras/`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
- `MyCiteV2/instances/_shared/portal_host/static/portal.css`

## Live Data Defects

### Invalid magnitude authority

- `deployed/fnd/data/payloads/cache/sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json:18` stores the active `msn-SAMRAS` magnitude.
- Under the historical V1 decode rules, that payload fails closed with:
  - `legacy address width must be positive`
- Result:
  - the live structure cannot be treated as a valid namespace authority

### Duplicate node bindings

- `deployed/fnd/data/sandbox/cts-gis/sources/sc.3-2-3-17-77-1-6-4-1-4.msn-administrative.json:55`
  - `3-2-3-17` is bound as `ohio`
- `...:57`
  - `3-2-3-17` is rebound as `Adams_County`
- `...:84-85`
  - `3-2-3-17-47` is duplicated as `lorain_county` and `Lucas_County`
- `...:149-152`
  - `3-2-3-17-77-1-9*` is bound for `new_franklin_city`
- `...:239-242`
  - the same `3-2-3-17-77-1-9*` branch is rebound for `reminderville_village`

### Summit County parent mismatch

- `...:114`
  - `summit_county` is stored at `3-2-3-17-76`
- `...:116`
  - descendants begin at `3-2-3-17-77-1`
- Result:
  - the live row overlays contradict their own parent-child lineage

### Misplaced `4-*` branch

- The requested `4-1..4-6` branch appears under `3-32..3-37` instead:
  - `...:325-330`
- The root `4` node itself does not appear until:
  - `...:335`
- Result:
  - the branch that should hang from root `4` is denoted under root `3`

### Placeholder title overlays

- Many descendant rows use `HERE` instead of an ASCII title payload:
  - for example `...:116-170`
- Result:
  - nodes exist in row form, but the title overlay is not decodable and must render blank under the contract

## Audit Conclusion

The historical authority is clear:

- SAMRAS magnitude defines structure
- node rows are overlays
- duplicate or out-of-namespace node rows are data defects, not alternate structure inputs

The live CTS-GIS data currently violates that contract in multiple ways, so the runtime now blocks navigation when magnitude or node-binding validity fails instead of fabricating a hierarchy from row overlays.
