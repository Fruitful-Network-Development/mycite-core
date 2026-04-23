# CTS-GIS Open Alignment Audit Plan

Date: 2026-04-23

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

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
- Remaining blocker is node `3-2-3-17-77-1-14`.

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

- `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md`
- follow-on CTS-GIS report updates published under `docs/audits/reports/`

## Exit Criteria

- Node `3-2-3-17-77-1-14` is resolved or explicitly waived.
- SAMRAS and datum-handling high-severity drifts are resolved or waived.
- CTS-GIS readiness gate reflects no untracked blockers.
- Remaining debt list has named owners and explicit closure path.
