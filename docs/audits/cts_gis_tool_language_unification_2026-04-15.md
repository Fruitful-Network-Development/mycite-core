# CTS-GIS Tool Language Unification Audit

Date: 2026-04-15

## Scope

- Canonicalize CTS-GIS public/tool language to `CTS-GIS` / `cts_gis` / `cts-gis`
- Keep shared shell terms stable: `Control Panel`, `Workbench`, `Interface Panel`, `tool_mediation_panel`, `tool_secondary_evidence`
- Add CTS-GIS-local body-carried state and a dedicated Interface Panel body for `Diktataograph` and `Garland`
- Preserve compatibility with legacy `maps` storage and request identifiers

## Findings

- CTS-GIS still exposed active repo/runtime language as `maps` in parts of the adapter and test corpus.
- The shell-composed CTS-GIS runtime dropped tool-local navigation state because the shell runtime did not forward extra request payload to the CTS-GIS bundle builder.
- The CTS-GIS Interface Panel still rendered the generic tool mediation panel rather than a CTS-GIS-local structural/profile body.
- CTS-GIS defaults were implicit in cross-domain ranking logic instead of being contract-level defaults.
- Repo docs did not clearly distinguish shared shell mediation subject from CTS-GIS-local structural navigation and correlated profile projection.

## Corrections

- Canonical public/tool naming now prefers `CTS-GIS`; legacy `maps` remains compatibility-only.
- The filesystem datum store now emits canonical CTS-GIS public ids for sandbox source documents while still loading legacy `maps` paths.
- The shell runtime now forwards CTS-GIS tool-local request payload so shell-dispatched CTS-GIS controls can remain body-carried.
- CTS-GIS request/runtime payloads now normalize one canonical `tool_state` shape with compatibility aliases for old mediation keys.
- CTS-GIS defaults are explicit:
  - `attention_node_id=3-2-3-17-77`
  - `intention_rule_id=descendants_depth_1_or_2`
  - `time_directive=""`
  - `archetype_family_id=samras_nominal`
- The dominant CTS-GIS Interface Panel now mounts one CTS-GIS-local interface body:
  - `Diktataograph`
  - `Garland`
- The CTS-GIS Control Panel now carries directive, AITAS, attention, projection-rule, and source-evidence groups.
- CTS-GIS workbench content remains secondary evidence and hidden by default.

## Terminology Normalization

- Shared shell vocabulary:
  - `Control Panel`
  - `Workbench`
  - `Interface Panel`
- CTS-GIS-local vocabulary:
  - `Diktataograph`
  - `Garland`
  - `Attention`
  - `Intention`
  - `Time`
  - `Archetype`
- Compatibility-only legacy vocabulary:
  - `maps`
  - legacy `mediation_state.intention_token`
  - legacy top-level row/feature selection keys

## Remaining Compatibility Notes

- Shared shell `AitasContext` remains unchanged.
- CTS-GIS uses richer NIMM/AITAS labels only inside tool-local request/runtime payloads.
- Legacy `maps` data, identifiers, and file names are still loadable until a later deliberate storage migration.
