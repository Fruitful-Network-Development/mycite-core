# CTS-GIS Runtime Readiness Report

Date: 2026-04-25

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-26`

## Purpose

Publish current CTS-GIS runtime readiness evidence for deployed behavior, with explicit separation between:

- source corpus structural/loadability readiness, and
- compiled-artifact/strict-runtime readiness.

## Initiative and Task Linkage

- Initiative: `INIT-CTS-GIS-OPEN-ALIGNMENT`
- Tasks:
  - `TASK-CTSGIS-RUNTIME-001` (done)
  - `TASK-CTSGIS-RUNTIME-002` (done)
  - `TASK-CTSGIS-RUNTIME-003` (done)
  - `TASK-CTSGIS-RUNTIME-004` (done)
  - `TASK-CTSGIS-SAMRAS-001` (blocked)
  - `TASK-CTSGIS-DATUM-001` (blocked)

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/cts_gis_compiled_artifact_contract.md`
- `docs/contracts/cts_gis_hops_profile_sources.md`
- `docs/contracts/cts_gis_precinct_cts_staging_sources.md`

## Scope and Inputs

Validated corpus under the live FND state root:

- `/srv/mycite-state/instances/fnd/data/sandbox/cts-gis/`

Validated runtime paths:

- `MyCiteV2/packages/adapters/filesystem/live_system_datum_store.py`
- `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`

## Findings

### 1) Source corpus structure/loadability: ready

Validated counts and JSON shape:

- tool anchor file: present and JSON-valid
  - `/srv/mycite-state/instances/fnd/data/sandbox/cts-gis/tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json`
- administrative source profile sets:
  - admin/state: `1` (`*.fnd.3-2-3-17.json`)
  - county: `1` (`*.fnd.3-2-3-17-77.json`)
- community profiles: `31`
- precinct profiles: `371`
- CTS-GIS sandbox JSON files total: `407`
- invalid JSON files: `0`

Filesystem datum-store catalog loading evidence:

- total authoritative docs: `409`
- CTS-GIS sandbox docs loaded: `406`
- anchor warnings: `0`
- catalog warnings: `0`

Task disposition:

- `TASK-CTSGIS-RUNTIME-002`: `done`

### 2) production_strict runtime readiness: ready

Root-cause and contract decision:

- The compiler had been deriving namespace roots from every dropdown option in the
  compiled navigation catalog.
- CTS-GIS SAMRAS root options `1..8` are sibling roots inside one decoded
  namespace, not eight separate namespaces.
- `strict_one_namespace_failed` was therefore a contract/model mismatch: the
  active lineage root was singular (`3`), but the dropdown catalog exposed all
  valid top-level roots.
- Contract decision recorded in:
  - `docs/contracts/cts_gis_compiled_artifact_contract.md`
  - `docs/contracts/cts_gis_hops_profile_sources.md`
- `one_namespace` now validates the active selected lineage root carried by
  `navigation_model.active_path` / `active_node_id`, not the total count of
  dropdown root options.

Compiled artifact state:

- expected path:
  - `/srv/mycite-state/instances/fnd/data/payloads/compiled/cts_gis.fnd.compiled.json`
- regeneration command:
  - `PYTHONPATH=. python3 MyCiteV2/scripts/compile_cts_gis_artifact.py --data-dir /srv/mycite-state/instances/fnd/data --private-dir /srv/mycite-state/instances/fnd/private --scope-id fnd`
- current compile output:
  - `invariants.valid=true`
  - `strict_invariants.one_authority=true`
  - `strict_invariants.one_namespace=true`
  - `strict_invariants.namespace_roots=["3"]`

Observed runtime behavior after regeneration:

- `runtime_mode=production_strict`
  - readiness: `ready`
  - navigation decode state: `ready`
  - map projection state: `projectable`
  - render feature count: `1`
  - warnings: `[]`

Task disposition:

- `TASK-CTSGIS-RUNTIME-001`: `done`
- `TASK-CTSGIS-RUNTIME-004`: `done`

### 3) Garland precinct overlay activation: normalized and evidenced

Normalized gate model:

- CTS-GIS now preserves anchor rows through datum-recognition projection so
  chronology gating is visible to the read-only service.
- `contextual_references.district_precincts` now reports:
  - `enabled`
  - `attention_node_id`
  - `supported_attention_lineage`
  - `chronological_anchor_present`
  - `time_token`
  - `timeframe_tokens`
  - `timeframe_match`
  - `gate_failures`
- Deterministic failure reasons now surface as stable gate codes such as:
  - `attention_lineage_unsupported`
  - `chronological_anchor_missing`
  - `district_timeframe_mismatch`
  - `time_context_inactive`

Negative gate evidence:

- County attention `3-2-3-17-77` with time token `23_present-district_31`
  stays fail-closed for precinct overlays because the selected county document
  exposes no matching district timeframe tokens.
- Runtime output records:
  - `gate_failures=["district_timeframe_mismatch"]`
  - warning:
    `Time context '23_present-district_31' is outside district timeframe scope; precinct overlays were skipped.`
- Synthetic unit coverage also proves unsupported lineage handling via
  `attention_lineage_unsupported`.

Positive gate evidence:

- Live state attention `3-2-3-17` with time token `23_present-district_31` and
  `precinct_district_overlay_enabled=true` now activates precinct overlays.
- Observed live output:
  - `overlay_active=true`
  - `gate_failures=[]`
  - `render_profile_count=372`
  - `render_feature_count=372`
  - trailing rendered precinct profiles include `247-17-77-95` through
    `247-17-77-99`
- Unit coverage also proves a synthetic county-level positive case where
  chronology + timeframe + supported lineage gates are all satisfied.

Task disposition:

- `TASK-CTSGIS-RUNTIME-003`: `done`

### 4) Hierarchical dropdown traversal and Ohio Garland anchoring: hardened

Runtime hardening in compiled-directory navigation:

- Compiled navigation now honors deterministic requested hierarchical active paths
  when they are valid in the compiled dropdown lineage, including Ohio selection
  path `3 -> 3-2 -> 3-2-3 -> 3-2-3-17`.
- Garland profile projection now remains anchored to the selected attention node
  from that deterministic path instead of drifting to compiled-default deeper
  descendants.
- Invalid/unresolved requests now surface deterministic diagnostics in
  `navigation_canvas.diagnostics`:
  - `invalid_active_path`
  - `unresolved_node_binding`

Test evidence:

- Added runtime unit coverage in:
  - `MyCiteV2/tests/unit/test_portal_cts_gis_runtime.py`
- Coverage proves:
  - deterministic compiled-path honoring for Ohio selection;
  - Garland profile anchoring to selected node;
  - explicit diagnostics for invalid/unresolved compiled-path requests.

Task disposition:

- `TASK-CTSGIS-RUNTIME-005`: `done`

## Lifecycle and Consolidation Decision

- Existing stream retained: `STREAM-CTS-GIS-OPEN` (extended, not replaced).
- Canonical active report for stream is now this file:
  - `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md`
- Historical completed SQL assurance baseline retained (not deleted):
  - `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`

## Remaining Open Work

1. Keep `TASK-CTSGIS-SAMRAS-001` blocked until structural/mutation/mediation
   drift matrices plus owner sign-off are published.
2. Keep `TASK-CTSGIS-DATUM-001` blocked until critical/high datum drift
   disposition matrices plus deterministic ordering/editing evidence are
   published.

## Validation Executed

Commands executed in this cycle:

- `python3` JSON validation/count scans over `/srv/mycite-state/instances/fnd/data/sandbox/cts-gis/**/*.json`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_compiled_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_read_only`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_cts_gis_runtime`
- `PYTHONPATH=. python3 MyCiteV2/scripts/compile_cts_gis_artifact.py --data-dir /srv/mycite-state/instances/fnd/data --private-dir /srv/mycite-state/instances/fnd/private --scope-id fnd`
- production strict bundle posture check using `build_portal_cts_gis_surface_bundle(...)`
- live precinct-overlay probes using `CtsGisReadOnlyService.read_surface(...)` for:
  - state attention `3-2-3-17`
  - county attention `3-2-3-17-77`

Environment note:

- `pytest` is unavailable in current environment (`No module named pytest`), so runtime/library-level Python checks were used for evidence capture in this cycle.
