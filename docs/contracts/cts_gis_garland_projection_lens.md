# CTS-GIS Garland Projection Lens

## Status

Canonical

## Purpose

Define how Garland visualizes projected CTS-GIS geometry and how viewport bounds are selected.

This contract is downstream of:

- `docs/contracts/cts_gis_hops_profile_sources.md`
- `docs/contracts/cts_gis_samras_addressing.md`

## Geometry Inputs

Garland consumes runtime `geospatial_projection` from CTS-GIS service/runtime payloads.

Expected payload fields:

- `feature_collection.type = "FeatureCollection"`
- `feature_collection.features[]` with `Polygon` or `MultiPolygon` geometry for map stage rendering
- `collection_bounds` as `[min_lon, min_lat, max_lon, max_lat]`
- `focus_bounds` as optional attention-profile bounds
- `selected_feature_bounds` as optional selected-feature bounds
- `selected_feature_explicit` as a bool indicating whether selected-feature focus came
  from an explicit user selection request
- `contextual_references` with additive context metadata (for example
  `time_context` and anchor-context summaries)

## Geometry Authority

Garland renders whatever geometry authority the service emits.

- HOPS-decoded geometry is authoritative whenever decode succeeds
- warning diagnostics do not change geometry authority
- `reference_geojson_fallback` appears when HOPS cannot produce projectable geometry or semantic guardrails reject the decoded shape
- semantic guardrails can request fallback when decode-valid geometry is implausible for node-level envelope policy

## Bounds And Focus Rules

Primary intent is to keep the viewport stable for the active profile while still supporting widened overlays.

1. Prefer `collection_bounds` when sane.
2. If `collection_bounds` is pathologically larger than `focus_bounds`, use `focus_bounds`.
3. If still pathological and `selected_feature_bounds` exists, use `selected_feature_bounds`
   only when `selected_feature_explicit=true`.
4. If no valid bounds are present, compute bounds from geometry points.

This prevents one outlier overlay member from collapsing the visible active shape.

## Projection Health

Garland surfaces service projection state through:

- `projection_state`: `inspect_only`, `projectable`, `projectable_degraded`, `projectable_fallback`
- `projection_health.state`: `empty`, `ok`, `degraded`, `fallback`
- `fallback_reason_codes`: machine-readable reason list
- `semantic_guardrails`: `{ triggered, reason_codes }` for semantic plausibility diagnostics

## Context Metadata

CTS-GIS may include additive context metadata that does not change navigation:

- `mediation_state.time` carries requested `time` context payload from the caller
- `mediation_state.anchor_context` summarizes supporting anchor adjunct rows
- `diagnostic_summary.time_context_active` signals active contextual request state
- when time context is active, widened overlays may include matching precinct
  cohort profiles for the active state/county attention lineage

These fields are contextual-only and do not change how `attention_node_id` and
`intention_token` are normalized.

## Non-Goals

- Garland does not redefine HOPS decode rules.
- Garland does not invent geometry from diagnostics.
- Garland does not treat title/overlay decode issues as map geometry authority changes.

## Promotion Coupling

Geometry quality regressions should be corrected through the reference-promotion
repair pipeline (`docs/contracts/cts_gis_reference_promotion_and_profile_repair.md`),
not by Garland-only behavior changes.
