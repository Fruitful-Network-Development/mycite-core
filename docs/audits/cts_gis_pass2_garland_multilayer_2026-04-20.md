# CTS-GIS Pass 2 Garland Multi-Layer Audit (2026-04-20)

## Scope

- Pass objective: harden intention-driven multi-layer projection in Garland.
- Focus areas:
  - intention overlay matrix (`self`, `children`, `descendants_depth_1_or_2`, `branch:*`)
  - projected profile/feature count consistency
  - attention-focused bounds behavior under explicit feature selection
  - runtime normalization behavior for invalid `branch:*` tokens

## Implementation Summary

- Added explicit matrix coverage for `branch:*` intention mode in service and runtime tests.
- Stabilized overlay assembly ordering in CTS-GIS service for children and feature-id merge ordering.
- Added runtime selection explicitness metadata:
  - `tool_state.selection.selected_feature_explicit`
  - `geospatial_projection.selected_feature_explicit`
- Updated Garland bounds selection logic to only prefer `selected_feature_bounds` when selection is explicit.
- Added runtime normalization assertion for invalid branch target fallback to `self`.

## Evidence

### Live corpus intention overlay counts

Command:

- `python3 -c ... CtsGisReadOnlyService.read_surface(...) ...`

Observed:

- `self`: `render_feature_count=1`, `feature_count=1`
- `children`: `render_feature_count=1`, `feature_count=1`
- `descendants_depth_1_or_2`: `render_feature_count=32`, `feature_count=32`
- `branch:3-2-3-17-77-1-1`: `render_feature_count=1`, `feature_count=1`

All tested modes maintained render-count consistency with map projection feature count.

### Explicit feature selection vs focus bounds

Command:

- `python3 -c ... build_portal_cts_gis_surface_bundle(...) ...`

Observed:

- `selected_feature_explicit=true`
- `selected_feature_id` resolved to the requested feature
- `focus_bounds_unchanged=true` relative to baseline descendants overlay request
- `selected_feature_bounds_present=true`

This confirms attention-focused bounds remain stable while explicit selection metadata is preserved.

## Test Coverage Added/Updated

- `MyCiteV2.tests.unit.test_cts_gis_read_only`
  - `test_branch_intention_renders_attention_plus_target_child_only`
- `MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
  - `test_cts_gis_branch_intention_overlays_attention_plus_target_child`
  - `test_cts_gis_explicit_feature_selection_does_not_replace_attention_focus_bounds`
  - `test_cts_gis_invalid_branch_intention_normalizes_to_self`

## Outcome

Pass 2 hardening achieved deterministic intention overlay behavior, explicit selection-aware Garland bounds control, and stronger normalization guarantees for runtime intention contracts.
