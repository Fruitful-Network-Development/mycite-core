# CTS-GIS Legacy `maps` Phase-A Alignment Audit

Date: 2026-04-16

## Scope

- Align v2.5.3.x CTS-GIS behavior to canonical naming while preserving one explicit phase-A compatibility path.
- Use commit-precedent direction from:
  - `79bd733` (`CTS-GIS Tool Language and Interface-Body Unification`)
  - `854365c` (`v2.5.3 Portal Shell Stabilization + Canonical Unification`)
  - `2926cc8` (`Portal Shell Peer-Region Normalization`)

## Corrections

- Added one shared CTS-GIS phase-A compat module:
  - `MyCiteV2/packages/ports/datum_store/cts_gis_legacy_compat.py`
- Replaced scattered inline legacy checks in:
  - runtime CTS-GIS surface builder
  - filesystem datum-store adapter
  - CTS-GIS read-only service
  - SYSTEM tool control-panel root selection
- Canonicalized deployed and live FND CTS-GIS storage paths:
  - `data/sandbox/cts-gis/tool.<msn>.cts-gis.json`
  - `private/utilities/tools/cts-gis/spec.json` with `tool_id=cts_gis`
- Preserved phase-A compatibility for legacy inbound aliases and introduced one warning code:
  - `cts_gis.legacy_maps_alias_consumed`

## Contract Notes

- Phase-A canonical outward contract remains:
  - route slug `cts-gis`
  - tool id `cts_gis`
  - sandbox document ids `sandbox:cts_gis:*`
- Phase-A legacy inbound aliases remain compatibility-only:
  - `maps` tool id
  - `sandbox:maps:*`
  - legacy anchor naming patterns
- Phase-B target (v2.5.4):
  - remove phase-A alias intake and warning path
  - remove phase-A legacy fixture and deprecation mapping entries

