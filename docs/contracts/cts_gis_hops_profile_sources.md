# CTS-GIS HOPS Profile Sources

## Status

Canonical

## Purpose

CTS-GIS profile source files do not store GeoJSON directly.

They store HOPS-backed profile rows that CTS-GIS decodes and projects into GeoJSON at runtime for Garland.

This document defines the row-chain contract used by source files such as:

- `data/sandbox/cts-gis/sources/<corpus>.fnd.<node>.json`

Within each file, the profile rows live under `datum_addressing_abstraction_space`.

## Runtime Rule

Garland emits GeoJSON at runtime.

The profile source file is a datum-addressing document, not a persisted `FeatureCollection`.

CTS-GIS currently does this in two steps:

1. decode `rf.3-1-1` HOPS coordinate tokens into `[longitude, latitude]`
2. assemble runtime GeoJSON features from those decoded coordinates

That means:

- the source file stores HOPS coordinate strings
- the source file does not store GeoJSON geometry arrays
- ring closure is applied by runtime assembly, not by duplicating the first point in every `4-*` row

## HOPS Encode/Decode Invariants

CTS-GIS treats HOPS coordinate strings as the canonical geometry authority whenever decoding succeeds.

- each coordinate slot in a `4-*` row must alternate as `rf.3-1-1`, `<hops-coordinate-token>`
- decode produces a numeric `[longitude, latitude]` pair for each valid token
- decoded coordinate order must preserve row order exactly
- ring closure is a render-time operation only (first coordinate appended at end)
- decode warnings are diagnostic metadata; they do not change geometry authority by themselves
- semantic guardrails may mark decode-valid geometry as implausible for the active node envelope

Decode-failure semantics:

- if a row has `reference_binding_count > 0` and `decoded_coordinate_count == 0`, the row is non-projectable from HOPS
- if only some tokens fail, the profile may be marked degraded, but decoded HOPS geometry remains authoritative
- `reference_geojson` is fallback-only for non-projectable rows/profiles or semantic-implausibility override, not a generic warning-triggered override
- semantic-guardrail reason codes are surfaced via runtime `fallback_reason_codes` (for example `semantic_bounds_outside_expected_envelope`)

## Source Loading And Overlay Assembly

- CTS-GIS source files and their supporting anchor documents remain strict JSON inputs; malformed JSON is surfaced as warnings rather than being parsed permissively.
- A malformed shared anchor blocks dependent HOPS projection recovery for the affected source files until that anchor is repaired.
- CTS-GIS source discovery includes both `data/sandbox/cts-gis/sources/*.json` and
  `data/sandbox/cts-gis/sources/precincts/*.json`.
- When node-focused intention widens to `<attention_node_id>-0` or `<attention_node_id>-0-0`, Garland may assemble one geospatial overlay from multiple in-scope projectable source documents.
- When `mediation_state.time.active=true`, widened overlays may additionally include
  precinct cohort profiles from `sources/precincts/` that match the active
  state/county attention lineage (for example `247-<state>-<county>-*` under
  `3-2-3-<state>-<county>` attention).
- That widened overlay does not change the active profile: `profile_projection` stays focused on the selected node while `geospatial_projection` collects the projectable features.
- Non-Garland row/detail views remain anchored to the currently selected document even when Garland overlays widen across multiple projectable sources.
- Garland lens projection and bounds behavior are defined in `docs/contracts/cts_gis_garland_projection_lens.md`.
- For widened overlays, `render_set_summary.render_feature_count` and
  `map_projection.feature_count` must stay aligned to the same projected profile set.

## Row Chain

CTS-GIS profile sources use a `4 -> 5 -> 6 -> 7` chain.

### `4-*` rows: coordinate rings

`4-<n>-1` rows store one polygon ring as `n` HOPS coordinate tokens.

Contract:

- anchor reference: `rf.3-1-1`
- datum layout after the row id alternates `rf.3-1-1`, `<hops-coordinate-token>`
- stored values: HOPS coordinate tokens
- row label: `polygon_*`
- `n` must equal the number of stored coordinate tokens

Example:

- `4-3878-1` stores 3878 HOPS vertices
- runtime closes that ring into a GeoJSON ring of 3879 positions by appending the starting point

### `5-*` rows: polygon members

`5-0-*` rows group one or more `4-*` rows into one polygon member.

Contract:

- row reference form: `~`
- payload entries after the row id are `4-*` row addresses
- the first referenced `4-*` row is the exterior ring
- any later referenced `4-*` rows are interior rings / holes
- references must be unique inside the `5-*` row

### `6-*` rows: collection wrapper

`6-*` rows group polygon members into one or more collections.

Contract:

- row reference form: `~`
- payload entries after the row id are `5-*` row addresses
- references must be unique inside each `6-*` row
- `6-0-1` is the primary boundary collection for the active profile owner row
- additional `6-*` collections (for example `6-0-2`) are allowed for additive
  profile sets such as precinct-group adjuncts

This row is the source-side equivalent of a runtime multi-member geometry collection.

### `7-*` rows: SAMRAS profile binding

`7-*` owner rows bind collected geometry to SAMRAS profile nodes.

Contract:

- anchor reference: `rf.3-1-2`
- primary SAMRAS node id must match the file suffix node id
- secondary SAMRAS node id may bind a deeper related profile node
- the first linked `6-*` row is the primary boundary collection used for the
  profile boundary chain
- additional `6-*` links may be preserved for additive collections

Example:

- file `...fnd.3-2-3-17-77-1-1.json`
- `7-3-1` primary node id: `3-2-3-17-77-1-1`

## GeoJSON Comparison Example

The Akron comparison gives a concrete example.

### Source datum

`sc.3-2-3-17-77-1-6-4-1-4.fnd.3-2-3-17-77-1-1.json` contains:

- 23 `4-*` rows
- 7 `5-*` rows
- 1 `6-*` row
- 1 `7-*` row

### Reference GeoJSON

`docs/personal_notes/city-of-akron.geojson` contains:

- 1 feature
- geometry type `MultiPolygon`
- 7 polygon members

### Structural correspondence

The chain lines up as:

- each `5-*` row corresponds to one GeoJSON polygon member
- `5-0-1` is the large Akron polygon with holes
- `5-0-2` through `5-0-7` are the smaller standalone polygon members
- the `4-*` row counts match the GeoJSON ring lengths minus the runtime closing point

For the first Akron polygon member, the GeoJSON ring sizes are:

- `3878, 9, 49, 6, 6, 15, 9, 21, 12, 41, 19, 34, 30, 24, 107, 31, 114`

Those correspond to the unique `4-*` rows linked from `5-0-1`.

## Validity Rules

CTS-GIS profile sources are valid only when all of the following hold:

- every referenced `4-*`, `5-*`, and `6-*` row exists
- every `5-*` row references unique `4-*` rows
- every `6-*` row references unique `5-*` rows
- every `4-<n>-1` row stores exactly `n` HOPS coordinate tokens
- a `7-*` owner row binds to the same primary SAMRAS node named by the file suffix
- the first owner-row `6-*` collection resolves to valid `5-*` and `4-*` rows

## Operational Consequence

When Garland shows a profile polygon, it is showing a runtime projection of the HOPS profile source chain, not a stored GeoJSON artifact.

So profile-source repairs should target:

- broken `4 -> 5 -> 6 -> 7` references
- wrong SAMRAS bindings in `7-3-1`
- incorrect `4-<n>-1` counts

They should not target Garland by hand-editing runtime GeoJSON into the source file.

## Promotion Workflow Requirement

New source onboarding and profile repair must follow the reference-promotion workflow
defined in `docs/contracts/cts_gis_reference_promotion_and_profile_repair.md`.

That workflow is the only approved path for converting vetted GeoJSON into
authoritative `4 -> 5 -> 6 -> 7` HOPS row chains.
