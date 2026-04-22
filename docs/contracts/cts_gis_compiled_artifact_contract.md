# CTS-GIS Compiled Artifact Contract

Schema id:

- `mycite.v2.portal.system.tools.cts_gis.compiled.v1`

Canonical storage path:

- `data/payloads/compiled/cts_gis.<scope_id>.compiled.json`

## Required Top-Level Fields

- `schema`
- `artifact_version`
- `generated_at`
- `portal_scope_id`
- `build_mode`
- `default_runtime_mode`
- `default_tool_state`
- `navigation_model`
- `projection_model`
- `evidence_model`
- `invariants`

## Runtime Invariants

`invariants.valid=true` is required for `production_strict`.

Current baseline invariant checks include:

- navigation decode readiness
- source evidence readiness

Additional invariant checks may be added as the compiler matures.

`strict_invariants.valid=true` is also required for `production_strict`.

Strict baseline checks include:

- exactly one SAMRAS authority source (`one_authority`)
- exactly one active namespace root in compiled navigation (`one_namespace`)

## Navigation Model

`navigation_model` carries:

- `decode_state`
- `source_authority`
- `active_node_id`
- `active_path[]`
- `dropdowns[]`

Compiled dropdown options are transport-safe and do not require raw authority reconstruction on each request.

## Projection Model

`projection_model` carries:

- `projection_state`
- `projection_source`
- `projection_health`
- `fallback_reason_codes`
- `focus_bounds`
- `feature_collection`
- `selected_feature`
- `profile_summary`

## Evidence Model

`evidence_model` carries:

- `source_evidence`
- `diagnostic_summary`
- `warnings`

Production callers may request lazy/minimal evidence while audit callers can request expanded evidence.
# CTS-GIS Compiled Artifact Contract

Schema id:

- `mycite.v2.portal.system.tools.cts_gis.compiled.v1`

Canonical storage path:

- `data/payloads/compiled/cts_gis.<scope_id>.compiled.json`

## Required Top-Level Fields

- `schema`
- `artifact_version`
- `generated_at`
- `portal_scope_id`
- `build_mode`
- `default_runtime_mode`
- `default_tool_state`
- `navigation_model`
- `projection_model`
- `evidence_model`
- `invariants`

## Runtime Invariants

`invariants.valid=true` is required for `production_strict`.

Current baseline invariant checks include:

- navigation decode readiness
- source evidence readiness

Additional invariant checks may be added as the compiler matures.

## Navigation Model

`navigation_model` carries:

- `decode_state`
- `source_authority`
- `active_node_id`
- `active_path[]`
- `dropdowns[]`

Compiled dropdown options are transport-safe and do not require raw authority reconstruction on each request.

## Projection Model

`projection_model` carries:

- `projection_state`
- `projection_source`
- `projection_health`
- `fallback_reason_codes`
- `focus_bounds`
- `feature_collection`
- `selected_feature`
- `profile_summary`

## Evidence Model

`evidence_model` carries:

- `source_evidence`
- `diagnostic_summary`
- `warnings`

Production callers may request lazy/minimal evidence while audit callers can request expanded evidence.
