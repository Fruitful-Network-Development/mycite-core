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
- `source_layout`
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
- validated source-layout readiness

Additional invariant checks may be added as the compiler matures.

`strict_invariants.valid=true` is also required for `production_strict`.

Strict baseline checks include:

- exactly one SAMRAS authority source (`one_authority`)
- exactly one active namespace root in compiled navigation (`one_namespace`)
- compiled `source_layout.fingerprint` matches the validated live CTS-GIS source
  corpus used by `production_strict`

Namespace note:

- a decoded SAMRAS namespace may legitimately expose multiple root dropdown
  options (`1..n`) inside one compiled catalog
- `one_namespace` validates the active selected lineage root carried by
  `navigation_model.active_path` / `active_node_id`, not the count of available
  root options in the dropdown catalog

## Source Layout

`source_layout` carries:

- `schema`
- `source_root`
- `precinct_root`
- `root_exists`
- `precinct_root_exists`
- `top_level_file_count`
- `precinct_file_count`
- `total_file_count`
- `sample_relative_paths[]`
- `fingerprint`

`production_strict` treats `source_layout.fingerprint` as a freshness contract.
If the validated live corpus fingerprint differs from the compiled artifact,
strict runtime fails closed instead of rebuilding from raw sources.

Canonical validator:

- `MyCiteV2/scripts/validate_cts_gis_sources.py`

## Navigation Model

`navigation_model` carries:

- `decode_state`
- `source_authority`
- `active_node_id`
- `active_path[]`
- `dropdowns[]`

Compiled dropdown options are transport-safe and do not require raw authority
reconstruction on each request.

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
- `contextual_references`

`projection_model` is the compiled default Garland snapshot seeded by
`default_tool_state`. When a valid `production_strict` request selects a
different node/time/overlay context, runtime may hydrate a request-specific
projection view from authoritative CTS-GIS projection documents while retaining
the compiled navigation/evidence baseline.

`projection_model.contextual_references` carries the Garland-side compiled
summary context needed to keep the profile panel transport-safe in
`production_strict`, including deferred district precinct collection summaries
that can be overlaid later without re-reading the full surface by default.

## Evidence Model

`evidence_model` carries:

- `source_evidence`
- `diagnostic_summary`
- `warnings`

Production callers may request lazy/minimal evidence while audit callers can
request expanded evidence.

## Compile / Validate Posture

Compile command:

- `PYTHONPATH=. python3 MyCiteV2/scripts/compile_cts_gis_artifact.py --data-dir /srv/mycite-state/instances/fnd/data --private-dir /srv/mycite-state/instances/fnd/private --scope-id fnd`

Validation command:

- `python3 MyCiteV2/scripts/validate_cts_gis_sources.py --data-dir /srv/mycite-state/instances/fnd/data --scope-id fnd --require-compiled-match`
