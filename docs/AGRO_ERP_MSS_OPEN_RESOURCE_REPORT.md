# AGRO ERP MSS Open-Resource Report

## Scope

This report captures the portal-core work completed to make the FND open MSS resource usable through the FND<->TFF contract path and render a read-only taxonomy hierarchy in AGRO ERP.

## What Was Implemented

- FND open resource remains published on the public card under `accessible.fnd_open_access_5_0_4_5_0_5`.
- Contract payloads for FND<->TFF now carry the same open resource context:
  - `owner_selected_refs` / `counterparty_selected_refs` include `5-0-4` and `5-0-5`.
  - `owner_mss` / `counterparty_mss` mirror the FND open-resource MSS bitstring.
  - `details.open_access_resources` includes metadata for the resource key and source datum paths.
- AGRO ERP default taxonomy input was updated from `fnd.4-0-2` to `fnd.5-0-4`.
- Inherited taxonomy resolution now supports a txa-oriented hierarchy build from decompiled MSS rows:
  - The hierarchy is derived from collection references plus txa magnitude paths.
  - Parent/child relationships are computed from path-prefix reduction.
  - Output is read-only and id/path based (titles/icons are intentionally not required at this stage).
- AGRO ERP hierarchy rendering is now recursive in the tool template.
- FND runtime now includes AGRO ERP in tool registration/mounting so the same hierarchy view can be opened on FND.

## Why This Fixes The Current Goal

The current goal is to prove that a compact MSS resource can be inherited and used as a functional data surface without copying full anthology state into the consuming portal.

This is now achieved by:

1. Publishing the MSS bitstring as a public/open FND resource.
2. Reflecting the same resource in the bilateral contract context.
3. Decoding (`uncompile`) MSS in AGRO ERP and rendering txa hierarchy only.

No edit surface is required for this phase; the result is a stable read-only hierarchy chart.

## Data-Engine Canonicality Notes

This implementation reinforces the core rule:

- semantic identity: canonical datum abstraction/path
- storage address: local anthology position (`layer-value_group-iteration`)

By decoding and consuming compact MSS rows through canonical references, tools avoid coupling to portal-local storage positions. This is the same basis needed for other shared datatype domains (ASCII, coordinates, events, etc.): fixed semantic abstraction paths with portable MSS encoding/decoding.

## Known Current Constraints

- MSS decode does not yet carry rich title/icon payloads for inherited rows.
- Hierarchy view is intentionally read-only.
- Contract seeding/build materialization should be kept aligned with live state files when re-materializing environments.

## Recommended Next Hardening Steps

1. Add explicit contract metadata for selected-source to selected-compact mapping (`selected_source_refs` + `selected_compact_refs`) to make root mapping deterministic without heuristics.
2. Add optional inherited label/icon sidecar in compact payload metadata for richer hierarchy rendering.
3. Add regression tests for:
   - foreign ref `fnd.5-0-4` resolving via contract MSS
   - hierarchy parent/child derivation from magnitude path prefixes
   - agreement between public-card MSS resource and contract MSS field payload.

