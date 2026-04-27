# CTS-GIS Runtime Readiness Report

Date: 2026-04-25

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

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
  - `TASK-CTSGIS-RUNTIME-005` (done)
  - `TASK-CTSGIS-RUNTIME-006` (done)
  - `TASK-CTSGIS-RUNTIME-007` (done)
  - `TASK-CTSGIS-RUNTIME-008` (done)
  - `TASK-CTSGIS-RUNTIME-009` (done)
  - `TASK-CTSGIS-RUNTIME-010` (done)
  - `TASK-CTSGIS-RUNTIME-011` (done)
  - `TASK-CTSGIS-RUNTIME-012` (done)
  - `TASK-CTSGIS-RUNTIME-013` (done)
  - `TASK-CTSGIS-SAMRAS-002` (supporting evidence published)
  - `TASK-CTSGIS-DATUM-002` (supporting evidence published)
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

### 5) 2026-04-27 deployed portal precinct/optimization follow-on: completed

Active follow-on scope:

- user-observed deployed symptom: pressing `Load compiled precincts` has no
  visible effect
- optimization/program input:
  `docs/personal_notes/code_optimization_report.md`

Bounded task injection:

- `TASK-CTSGIS-RUNTIME-007`: restore deployed precinct-toggle request parity
- `TASK-CTSGIS-RUNTIME-008`: keep `production_strict` Garland precinct context
  lightweight and toggle-ready via compiled summaries
- `TASK-CTSGIS-RUNTIME-009`: convert optimization recommendations into bounded
  deployed-portal execution backlog

Supporting evidence surface:

- `docs/audits/reports/cts_gis_deployed_portal_precinct_optimization_follow_on_2026-04-27.md`

Outcome summary:

- shared portal dispatch now preserves CTS-GIS `runtime_mode` for Garland
  precinct-toggle action requests
- compiled artifacts now preserve Garland
  `projection_model.contextual_references` so `production_strict` remains
  toggle-ready with deferred precinct summaries
- optimization recommendations from
  `docs/personal_notes/code_optimization_report.md` are translated into a
  bounded supporting backlog without widening the active due-task queue

Task disposition:

- `TASK-CTSGIS-RUNTIME-007`: `done`
- `TASK-CTSGIS-RUNTIME-008`: `done`
- `TASK-CTSGIS-RUNTIME-009`: `done`

### 6) Source-layout validation, strict freshness, and compile-before-deploy posture: completed

Outcome summary:

- CTS-GIS source layout is now validated against the live FND
  `sources/` plus `sources/precincts/` corpus instead of relying on implicit
  monolithic-file assumptions.
- Compiled artifacts now carry a deterministic `source_layout.fingerprint`.
- `production_strict` rejects stale/mismatched artifacts and does not silently
  rebuild.
- Compile-before-restart posture is now enforced for FND deployment workflows.

Observed evidence:

- validated live file counts:
  - top-level source files: `35`
  - precinct source files: `371`
  - total source files: `406`
- validated fingerprint:
  - `56df73413996d516d774ac05c9729f5ae8b4c74a3feabf00d03ad8dc4bab3c4e`
- canonical validation command:
  - `python3 MyCiteV2/scripts/validate_cts_gis_sources.py --data-dir /srv/mycite-state/instances/fnd/data --scope-id fnd --require-compiled-match`
- canonical compile command:
  - `PYTHONPATH=. python3 MyCiteV2/scripts/compile_cts_gis_artifact.py --data-dir /srv/mycite-state/instances/fnd/data --private-dir /srv/mycite-state/instances/fnd/private --scope-id fnd`

Task disposition:

- `TASK-CTSGIS-RUNTIME-010`: `done`
- `TASK-CTSGIS-RUNTIME-011`: `done`
- `TASK-CTSGIS-RUNTIME-012`: `done`
- `TASK-CTSGIS-RUNTIME-013`: `done`

## Lifecycle and Consolidation Decision

- Existing stream retained: `STREAM-CTS-GIS-OPEN` (extended, not replaced).
- Canonical active report for stream is now this file:
  - `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md`
- Supporting follow-on analysis retained under the same stream:
  - `docs/audits/reports/cts_gis_deployed_portal_precinct_optimization_follow_on_2026-04-27.md`
- Historical completed SQL assurance baseline retained (not deleted):
  - `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`

## Remaining Open Work

1. Keep `TASK-CTSGIS-SAMRAS-001` blocked until structural/mutation/mediation
   drift matrices move from published evidence to explicit owner acknowledgment.
2. Keep `TASK-CTSGIS-DATUM-001` blocked until critical/high datum drift
   disposition matrices move from published evidence to explicit owner
   acknowledgment.

## Validation Executed

Commands executed in this cycle:

- `python3` JSON validation/count scans over `/srv/mycite-state/instances/fnd/data/sandbox/cts-gis/**/*.json`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_compiled_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_read_only`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_cts_gis_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `PYTHONPATH=. python3 MyCiteV2/scripts/compile_cts_gis_artifact.py --data-dir /srv/mycite-state/instances/fnd/data --private-dir /srv/mycite-state/instances/fnd/private --scope-id fnd`
- production strict bundle posture check using `build_portal_cts_gis_surface_bundle(...)`
- compiled artifact `contextual_references` probe over `/srv/mycite-state/instances/fnd/data/payloads/compiled/cts_gis.fnd.compiled.json`
- live precinct-overlay probes using `CtsGisReadOnlyService.read_surface(...)` for:
  - state attention `3-2-3-17`
  - county attention `3-2-3-17-77`

Environment note:

- `pytest` is unavailable in current environment (`No module named pytest`), so runtime/library-level Python checks were used for evidence capture in this cycle.
