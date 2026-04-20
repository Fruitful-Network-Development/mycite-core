# CTS-GIS Polygon Forensics (3-2-3-17-77)

## Scope

Investigate the polygon regression where node `3-2-3-17-77` decodes as valid HOPS but renders an incorrect geography, then implement deterministic guardrails and fallback diagnostics without changing source data.

## Reproduction Evidence

Runtime payload capture against deployed `fnd` data:

- `attention_node_id`: `3-2-3-17-77`
- `intention_token`: `self`
- `projection_source`: `hops`
- `projection_state`: `projectable_degraded`
- `decode_summary`: `reference_binding_count=1506`, `decoded_coordinate_count=1506`, `failed_token_count=0`
- `feature_collection.bounds`: `[-143.9995832766457, -35.638916901758876, -136.80223579113442, 35.98117875793889]`
- `fallback_reason_codes`: `semantic_bounds_outside_expected_envelope`, `semantic_span_exceeds_expected_envelope`

This reproduces the decode-valid/geo-invalid condition: HOPS decoding succeeds numerically, but resulting geometry is semantically implausible for Summit.

## Root Cause Chain

1. HOPS decoding currently validates syntactic/radix correctness, not local geographic plausibility.
2. The affected source rows produce legal longitude/latitude values, but those values drift outside expected Summit envelope.
3. Reference fallback was previously decode-failure-oriented only, so decode-success outliers stayed authoritative.
4. Garland correctly rendered the emitted geometry, so the defect originated in projection authority selection, not map rendering.

## Options Considered

1. **Keep strict HOPS with no semantic checks**  
   Rejected: preserves wrong polygon as `projectable` and provides no deterministic operator signal.

2. **Always prefer reference geometry when present**  
   Rejected: over-corrects and violates HOPS-first authority for healthy decode paths.

3. **Semantic guardrails + targeted fallback (selected)**  
   Accepted: maintain HOPS-first behavior, mark implausible geometry deterministically, and switch to reference fallback only when available.

## Implemented Changes

- Added semantic geometry guardrails in CTS-GIS projection service:
  - node-aware envelope checks for Summit county focus node
  - machine-readable reason codes:
    - `semantic_bounds_outside_expected_envelope`
    - `semantic_span_exceeds_expected_envelope`
- Added authority switching behavior:
  - if semantic guardrails trigger and `reference_geojson` is available for the active profile, use `reference_geojson_fallback`
  - if no trusted fallback exists, keep HOPS geometry but force degraded health with semantic reason codes
- Added inspector-facing diagnostics:
  - `map_projection.fallback_reason_codes` now carries semantic reason codes
  - `map_projection.semantic_guardrails` exposes `{ triggered, reason_codes }`
  - feature properties include `projection_reason_codes`

## Before/After Behavior Snapshots

- **Before**
  - decode-valid geometry for `3-2-3-17-77` could remain `projectable` with no semantic warning
  - fallback reasons emphasized decode failure/parity only

- **After**
  - decode-valid but geo-invalid geometry is explicitly marked degraded with semantic reason codes
  - reference fallback activates for semantic failures when trusted reference geometry exists
  - no-fallback scenarios remain visible and auditable without silently changing authority

## Validation

- Added regression tests for semantic-implausible decode paths:
  - with reference fallback available -> `projectable_fallback`
  - without reference fallback -> `projectable_degraded` (HOPS retained, semantic reason codes present)
- Existing CTS-GIS read-only unit suite remains passing after guardrail integration.

## Residual Risk

- Guardrail envelope is currently targeted to Summit county node `3-2-3-17-77`; additional corpora will require explicit envelope policy or metadata hints.
- When no trusted fallback is present, output remains degraded HOPS (diagnosed but not auto-repaired). Source repair remains the long-term corrective path.
