# CTS-GIS Deployed Portal Precinct Optimization Follow-On

Date: 2026-04-27

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Purpose

Capture the deployed portal follow-on created from the user-observed CTS-GIS
symptom that pressing `Load compiled precincts` has no visible effect, while
translating `docs/personal_notes/code_optimization_report.md` into bounded,
traceable work inside the existing CTS-GIS open stream.

## Initiative and Task Linkage

- Initiative: `INIT-CTS-GIS-OPEN-ALIGNMENT`
- Stream: `STREAM-CTS-GIS-OPEN`
- Tasks:
  - `TASK-CTSGIS-RUNTIME-007` (done)
  - `TASK-CTSGIS-RUNTIME-008` (done)
  - `TASK-CTSGIS-RUNTIME-009` (done)
  - `TASK-CTSGIS-RUNTIME-010` (done)
  - `TASK-CTSGIS-RUNTIME-011` (done)
  - `TASK-CTSGIS-RUNTIME-012` (done)
  - `TASK-CTSGIS-RUNTIME-013` (done)

## Canonical Relationship

- Canonical active plan remains:
  `docs/audits/cts_gis_open_alignment_audit_plan_2026-04-23.md`
- Canonical active report remains:
  `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md`
- This file is a supporting follow-on analysis/report and does not replace the
  canonical CTS-GIS runtime report.

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/cts_gis_compiled_artifact_contract.md`
- `docs/contracts/cts_gis_hops_profile_sources.md`
- `docs/contracts/cts_gis_samras_addressing.md`

## Inputs

- user-observed deployed symptom: pressing `Load compiled precincts` has no
  visible effect
- optimization source note:
  `docs/personal_notes/code_optimization_report.md`
- active runtime/control surfaces:
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`
  - `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
  - `MyCiteV2/packages/modules/cross_domain/cts_gis/compiled_artifact.py`

## Findings

### 1) The deployed symptom belongs to the existing CTS-GIS runtime stream, not a new stream

Why this stays in `STREAM-CTS-GIS-OPEN`:

- the Garland profile panel already exposes a district precinct toggle surface
- the CTS-GIS runtime already defines precinct overlay shell-request shaping and
  overlay-state mutation
- the remaining gap is request parity and compiled-context alignment for the
  deployed portal, not a separate product area

Decision:

- extend the existing stream/initiative
- keep the canonical CTS-GIS plan and canonical runtime report unchanged
- inject new runtime follow-on tasks instead of opening a second active stream

### 2) `TASK-CTSGIS-RUNTIME-007`: completed precinct-toggle request parity across portal dispatch and CTS-GIS runtime

Control points that must stay aligned:

- renderer binding:
  `v2_portal_inspector_renderers.js` binds `district_toggle` entries to either
  `shell_request` or `action`
- shared portal dispatch:
  `v2_portal_shell_core.js` shapes runtime action requests from the current
  envelope and is the highest-risk place for runtime-mode/request-parity drift
- CTS-GIS runtime mutation:
  `portal_cts_gis_runtime.py` owns
  `source.precinct_district_overlay_enabled`, selection resets, and the overlay
  transition outcome

Task mapping:

- `TASK-CTSGIS-RUNTIME-007` covers this control-path parity work

Implemented closure:

- `v2_portal_shell_core.js` now forwards `runtime_mode` when shared portal
  dispatch issues CTS-GIS runtime action requests, preventing the Garland
  precinct toggle from silently dropping the active runtime posture.
- `build_portal_cts_gis_surface_bundle(...)` now stamps `runtime_mode` into the
  generated CTS-GIS shell request base so the toggle works through both
  shell-request and direct-action paths.
- `_apply_cts_gis_action(...)` in `portal_cts_gis_runtime.py` now accepts the
  explicit `toggle_overlay` action and mutates
  `source.precinct_district_overlay_enabled` with deterministic selection reset
  behavior.

Observed evidence:

- `test_cts_gis_precinct_toggle_shell_request_preserves_runtime_mode_and_transitions_overlay_state`
  proves the Garland toggle shell request keeps `runtime_mode=audit_forensic`
  and transitions precinct collections out of `deferred`.
- `test_cts_gis_toggle_overlay_action_updates_tool_state_and_transitions_precinct_state`
  proves the direct runtime action path enables overlay state and loaded
  precinct collections.

### 3) `TASK-CTSGIS-RUNTIME-008`: completed compiled Garland precinct-context carry-forward for `production_strict`

Implemented closure:

- `compiled_artifact.py` now carries `service_surface.contextual_references`
  into `projection_model.contextual_references`.
- `portal_cts_gis_runtime.py` now restores compiled
  `projection_model.contextual_references` into the service-surface fallback
  used by `production_strict`, instead of synthesizing an empty Garland
  precinct summary.
- `cts_gis_compiled_artifact_contract.md` now records
  `projection_model.contextual_references` as required compiled Garland summary
  context for deferred district precinct collections.

Observed evidence:

- live compile command regenerated
  `/srv/mycite-state/instances/fnd/data/payloads/compiled/cts_gis.fnd.compiled.json`
  with `strict_invariants.valid=true`, `one_authority=true`,
  `one_namespace=true`, and `namespace_roots=["3"]`.
- live compiled artifact probe confirmed:
  - `projection_model.contextual_references` present
  - `district_precincts.collection_count=1`
  - first collection `summary_state=deferred`
- live `production_strict` bundle probe confirmed:
  - `runtime_mode=production_strict`
  - toggle shell request preserves `runtime_mode=production_strict`
  - Garland precinct collection remains present in deferred form before overlay
    activation

### 4) `TASK-CTSGIS-RUNTIME-009`: completed bounded optimization backlog translation

The optimization report supports a compiled-first follow-on, not heavier default
runtime logic.

Actionable considerations pulled from
`docs/personal_notes/code_optimization_report.md`:

- keep production on compiled artifacts instead of widening fallback rebuilds
- preserve thin runtime behavior and move context shaping into precompiled
  artifacts where possible
- modularize large precinct/HOPS sources only as bounded follow-on work with
  validation evidence
- make cache/invalidation and diagnostic-only paths explicit instead of mixing
  them into the default deployed portal path

Task mapping:

- `TASK-CTSGIS-RUNTIME-008` covers lightweight compiled-context alignment
- `TASK-CTSGIS-RUNTIME-009` covers bounded follow-on optimization backlog

Bounded backlog output retained without injecting new due tasks in this cycle:

1. Precinct/HOPS source modularization candidate
   - scope: break oversized precinct-supporting source documents into smaller
     validated units only after current deployed parity work is stable
   - evidence expectation: source inventory + modularization proposal linked to
     CTS-GIS authority contracts
   - validation expectation: JSON shape scan, compile command, and read-only
     loader parity tests once live fixture availability is normalized
2. Compiled artifact freshness/invalidation candidate
   - scope: tighten artifact staleness detection using generated metadata rather
     than widening runtime fallback
   - evidence expectation: contract/update note plus runtime invalidation rules
   - validation expectation: compile command, compiled-runtime unit coverage,
     and production-strict bundle probe
3. Diagnostic-path retirement/isolation candidate
   - scope: keep `audit_forensic` diagnostic rebuild paths explicitly separate
     from the default deployed portal posture
   - evidence expectation: runtime contract delta and bounded fallback owner
     notes
   - validation expectation: workspace runtime tests plus one-shell integration
     coverage

### 5) The right backlog split is immediate parity first, optimization second

Execution order:

1. `TASK-CTSGIS-RUNTIME-007`
   - restore deployed precinct-toggle effect and request parity
2. `TASK-CTSGIS-RUNTIME-008`
   - keep `production_strict` toggle-ready using compiled Garland summaries
3. `TASK-CTSGIS-RUNTIME-009`
   - convert larger optimization ideas into separately evidenced follow-on work

This keeps the user-visible defect from being buried under larger refactor work.

### 6) `TASK-CTSGIS-RUNTIME-010/011/012/013`: completed strict-source-layout, freshness, diagnostic isolation, and deploy enforcement follow-on

Implemented closure:

- live CTS-GIS `sources/` plus `sources/precincts/` layout is now codified by
  `build_cts_gis_source_layout_summary(...)` and
  `validate_cts_gis_source_layout(...)`
- compiled artifacts now record `source_layout.fingerprint`, and
  `production_strict` rejects stale or mismatched artifacts without silently
  rebuilding
- diagnostic rebuild/write behavior is isolated to explicit forensic flows, with
  runtime evidence distinguishing compiled-only reads from refresh events
- `deploy_portal_update.sh` now enforces compile-before-restart posture for FND
  unless intentionally skipped for diagnostics

Observed evidence:

- `python3 MyCiteV2/scripts/validate_cts_gis_sources.py --data-dir /srv/mycite-state/instances/fnd/data --scope-id fnd --require-compiled-match`
  reports `source_layout_valid=true` with `top_level_file_count=35`,
  `precinct_file_count=371`, `total_file_count=406`, and fingerprint
  `56df73413996d516d774ac05c9729f5ae8b4c74a3feabf00d03ad8dc4bab3c4e`
- `PYTHONPATH=. python3 MyCiteV2/scripts/compile_cts_gis_artifact.py --data-dir /srv/mycite-state/instances/fnd/data --private-dir /srv/mycite-state/instances/fnd/private --scope-id fnd`
  regenerates a strict-valid compiled artifact against that fingerprint
- `benchmarks/results/cts_gis_production_strict_probe_2026-04-27.json`
  confirms `compiled_artifact_valid=true`, `warnings=[]`, and strict runtime
  readiness against the validated source layout

Task mapping:

- `TASK-CTSGIS-RUNTIME-010`: closed
- `TASK-CTSGIS-RUNTIME-011`: closed
- `TASK-CTSGIS-RUNTIME-012`: closed
- `TASK-CTSGIS-RUNTIME-013`: closed

## Lifecycle and Consolidation Decision

- stream/initiative extended, not replaced
- no new stream opened
- canonical active plan/report preserved
- this file added as supporting follow-on analysis so canonical vs supporting
  report posture stays explicit

## Validation Executed

Commands executed in this change:

- `python3 -c "import pathlib, yaml; [yaml.safe_load(path.read_text(encoding='utf-8')) for path in pathlib.Path('docs/plans').glob('*task_board.yaml')]; [yaml.safe_load(path.read_text(encoding='utf-8')) for path in pathlib.Path('docs/plans').glob('*manifest.yaml')]; print('yaml-ok')"`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_compiled_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
- `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_read_only`
- live compiled-artifact probe over `/srv/mycite-state/instances/fnd/data/payloads/compiled/cts_gis.fnd.compiled.json`
- live `production_strict` Garland bundle probe using `build_portal_cts_gis_surface_bundle(...)`
- `python3 MyCiteV2/scripts/validate_cts_gis_sources.py --data-dir /srv/mycite-state/instances/fnd/data --scope-id fnd --require-compiled-match`
- `python3 -m unittest MyCiteV2.tests.unit.test_cts_gis_read_only`

Observed results:

- compile command: `passed`
- YAML surface validation: `passed`
- `test_cts_gis_compiled_runtime`: `passed` (`6` tests, `1` skipped)
- `test_portal_workspace_runtime_behavior`: `passed` (`42` tests, `19` skipped)
- `test_contract_docs_alignment`: `passed` (`13` tests)
- `test_portal_host_one_shell`: `passed` with environment skips (`6` skipped)
- live compiled-artifact probe: `passed`
- live `production_strict` Garland bundle probe: `passed`
- `test_cts_gis_read_only`: `failed` in this workspace because several
  live-Summit fixture expectations under
  `/srv/repo/mycite-core/deployed/fnd/data/sandbox/cts-gis/sources/` are not
  present, producing `FileNotFoundError` and downstream `NoneType`/lookup
  errors in the read-only live-data cases

Environment note:

- This report captures planning/task injection and validation of the current
  CTS-GIS implementation slice; deployment itself is not performed from this
  document change.
