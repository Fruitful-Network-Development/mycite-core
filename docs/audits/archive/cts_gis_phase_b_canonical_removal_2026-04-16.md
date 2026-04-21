# CTS-GIS Phase-B Canonical Removal Audit

Date: 2026-04-16

## Scope

- Complete v2.5.4 hard-removal of legacy CTS-GIS `maps` alias behavior.
- Keep CTS-GIS runtime, store, and contracts canonical-only.

## Canonical Contract State

- Tool id: `cts_gis`
- Tool slug/route segment: `cts-gis`
- Sandbox document ids: `sandbox:cts_gis:*`
- CTS-GIS anchor file: `tool.<msn>.cts-gis.json`

## Removals

- Deleted phase-A compat module:
  - `MyCiteV2/packages/ports/datum_store/cts_gis_legacy_compat.py`
- Removed alias rewrites and deprecation warnings from:
  - CTS-GIS runtime normalization/source-evidence
  - CTS-GIS read-only service document matching
  - filesystem datum-store anchor/tool-id handling
  - SYSTEM tool control-panel CTS-GIS root fallback logic
- Removed phase-A warning usage:
  - `cts_gis.legacy_maps_alias_consumed`

## Runtime/API Behavior

- Legacy alias request inputs are now rejected with:
  - HTTP `400`
  - `error.code=legacy_maps_alias_unsupported`
- Rejection is enforced for CTS-GIS request slots carrying legacy document ids, including top-level, mediation-state, and tool-state source fields.

## Migration Note

- Stale pre-phase-B roots should be removed or ignored during rollout:
  - `data/sandbox/maps`
  - `private/utilities/tools/maps`
