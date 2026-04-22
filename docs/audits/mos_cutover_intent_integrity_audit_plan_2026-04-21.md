# MOS Cutover Intent Integrity Audit Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-22`

## Purpose

Audit whether the MOS SQL cutover still reflects intended operation from
`docs/personal_notes/MOS/` at the level of behavior, not just file presence.
Focus on hidden drift risks where runtime contracts appear valid but semantic
intent has shifted. This plan is completed by
`docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md`.

## Intent Source Set

- `docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md`
- `docs/personal_notes/MOS/data_base_use_findings.md`
- `docs/personal_notes/MOS/mycelial_ontological_schema.md`
- `docs/personal_notes/MOS/mos_novelty_definition.md`
- `docs/personal_notes/MOS/legacy_cleanup_assesment_and_final_consolidation.md`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`
- `docs/plans/master_plan_mos.md`
- `docs/plans/mos_semantic_gate_register_2026-04-21.md`

## Audit Workstreams

### 1) Intent-to-canon crosswalk drift

Verify each still-relevant personal-note intention has a concrete canonical
counterpart and test/runtime evidence.

Deliverable:

- matrix with status per intent: `preserved|narrowed|deferred|broken`.

### 2) Semantic identity invariants

Re-check version identity, hyphae identity, and row-order/edit assumptions
against live SQL semantics and contract claims.

Deliverable:

- drift log for identity semantics with severity and owner.

### 3) Authority boundary posture

Ensure SQL authority remains primary for migrated `SYSTEM` surfaces and that any
filesystem use is explicit non-authoritative exception scope.

Deliverable:

- authority-boundary report with exception classification.

### 4) Hidden regression traps

Find low-visibility contract drifts (payload location changes, renderer fallback
paths, stale bootstrap assumptions, compatibility aliases that mask breakage).

Deliverable:

- high-leverage trap list with reproducible checks.

## Verification Matrix

For each finding, capture:

- severity: `critical|high|medium|low`
- drift class: `preserved|narrowed|deferred|broken`
- evidence: personal-note clause, contract section, code path, runtime payload
- verification: test path or command
- remediation type: `keep|clarify|fix|waive`

## Exit Criteria

- Every intended operational facet is classified with evidence in
  `docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md`.
- The named high-severity hidden drift around `/portal/system` render
  realization is fixed rather than waived.
- Hidden regression traps now have concrete manifest/registration/source-guard
  checks.
- The published closure report records current MOS realities without reopening
  closure.
