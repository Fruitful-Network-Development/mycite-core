# CTS-GIS Open Alignment Audit Plan

Date: 2026-04-23

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-27`

## Purpose

Consolidate remaining CTS-GIS open audit work into one active plan so blocker
resolution, SAMRAS rule alignment, and datum-handling alignment operate under one
closure queue and one readiness posture.

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/contracts/cts_gis_samras_addressing.md`
- `docs/contracts/cts_gis_hops_profile_sources.md`
- `docs/contracts/samras_structural_model.md`
- `docs/contracts/samras_validity_and_mutation.md`
- `docs/contracts/samras_engine_ui_boundary.md`

## Consolidated Sources

This plan consolidates:

- `docs/audits/cts_gis_source_hops_audit_plan_2026-04-20.md`
- `docs/audits/cts_gis_samras_rule_alignment_audit_plan_2026-04-20.md`
- `docs/audits/cts_gis_datum_handling_alignment_audit_plan_2026-04-20.md`

Those files are retained as historical deep-detail references and no longer serve as
the canonical active entrypoint.

## Active Workstreams

### 1) Source-hops blocker closure

Current status:

- Summit lineage verification is largely complete (`0 flagged / 32 clean`).
- Node `3-2-3-17-77-1-14` is dispositioned in the readiness gate via explicit
  waiver `WAIVER-CTSGIS-2026-04-24-001` in
  `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`.
- Underlying data gap remains open (no deployed source profile and no vetted
  reference mapping), and is carried as residual risk rather than hidden debt.

Required closure:

- provide deployed source profile plus vetted reference mapping, or
- record explicit readiness waiver in the CTS-GIS parity gate.

### 2) SAMRAS structural/mutation/mediation alignment

Required closure:

- structural rule matrix complete with drift classifications
- mutation invariants checklist complete
- mediation/projection parity findings resolved or waived

### 3) Datum handling alignment

Required closure:

- close critical/high drifts for identity, source precedence, ordering/editing,
  and runtime projection parity
- keep compatibility behavior explicit and bounded

## Unified Validation Gates

1. **Single authority gate**
   - no second routing/state/data authority path introduced
2. **Contract-first gate**
   - normative behavior is contract-linked and test-backed
3. **Determinism gate**
   - identical inputs/commands produce stable outputs
4. **Readiness gate**
   - blocker queue is empty or explicitly waived with rationale and evidence

## Primary Evidence Targets

- `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md`
- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md` (historical baseline)
- follow-on CTS-GIS report updates published under `docs/audits/reports/`

## 2026-04-25 Runtime Readiness Extension

This stream is extended (not replaced) with four runtime-readiness tasks:

- `TASK-CTSGIS-RUNTIME-001`: restore `production_strict` compiled artifact readiness
- `TASK-CTSGIS-RUNTIME-002`: verify source corpus structure/loadability for tool anchor + admin + community + precinct sets
- `TASK-CTSGIS-RUNTIME-003`: normalize precinct overlay activation gates and evidence
- `TASK-CTSGIS-RUNTIME-004`: resolve strict namespace invariant mismatch for compiled artifact validation

Follow-on extension for hierarchical navigation + profile correlation:

- `TASK-CTSGIS-RUNTIME-005`: harden deterministic hierarchical dropdown traversal for attention-path selection (`3` -> `3-2` -> `3-2-3` -> `3-2-3-17`) and ensure Garland projection anchors to the selected Ohio context without frontend-synthesized fallback state.

Follow-on extension for deployed portal precinct parity + optimization alignment:

- `TASK-CTSGIS-RUNTIME-006`: unify CTS-GIS Interface Panel tab hosting on the shared presentation-surface base
- `TASK-CTSGIS-RUNTIME-007`: restore deployed `Load compiled precincts` request parity across shared portal dispatch and CTS-GIS runtime
- `TASK-CTSGIS-RUNTIME-008`: carry compiled Garland precinct-context summaries so `production_strict` stays lightweight and toggle-ready
- `TASK-CTSGIS-RUNTIME-009`: translate `docs/personal_notes/code_optimization_report.md` into a bounded deployed-portal execution backlog

Initiative linkage:

- Compatibility initiative: `INIT-CTS-GIS-OPEN-ALIGNMENT`
- Context stream: `STREAM-CTS-GIS-OPEN`

Execution status:

- `TASK-CTSGIS-RUNTIME-005` is completed with evidence in:
  - `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md`
  - `MyCiteV2/tests/unit/test_portal_cts_gis_runtime.py`
- `TASK-CTSGIS-RUNTIME-006` is completed with evidence in:
  - `docs/audits/reports/cts_gis_runtime_readiness_report_2026-04-25.md`
  - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
- `TASK-CTSGIS-RUNTIME-007/008/009` are completed follow-on work from
  `2026-04-27`, closing deployed precinct-toggle parity, compiled Garland
  summary carry-forward, and bounded optimization backlog translation with
  evidence in
  `docs/audits/reports/cts_gis_deployed_portal_precinct_optimization_follow_on_2026-04-27.md`.

Lifecycle decision:

- Keep this file as the canonical active plan for `STREAM-CTS-GIS-OPEN`.
- Keep `cts_gis_sql_authority_assurance_report_2026-04-21.md` as retained completed history.
- Use `cts_gis_runtime_readiness_report_2026-04-25.md` as the canonical active report for current runtime posture.
- Keep `cts_gis_deployed_portal_precinct_optimization_follow_on_2026-04-27.md`
  as a supporting follow-on analysis/report; it does not replace the canonical
  CTS-GIS runtime report unless the manifests are updated in a later change.

## Exit Criteria

- Node `3-2-3-17-77-1-14` is resolved or explicitly waived.
- SAMRAS and datum-handling high-severity drifts are resolved or waived.
- CTS-GIS readiness gate reflects no untracked blockers.
- Remaining debt list has named owners and explicit closure path.
