# Code Bloat Remediation Execution Plan

Date: 2026-04-25

Doc type: `program-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-25`

## Planning Registry

- Stream ID: `STREAM-CODE-BLOAT-REMEDIATION`
- Compatibility initiative ID: `INIT-CODE-BLOAT-REMEDIATION`
- Canonical active report:
  `docs/audits/reports/code_bloat_remediation_execution_report_2026-04-25.md`
- Upstream diagnosis seed: `docs/audits/reports/code_bloat_diagnosis.md`
- Upstream planning stream: `STREAM-CODE-BLOAT-DEEP-AUDIT` (completed)

## Purpose

Execute corrective work derived from completed code-bloat audits by converting
findings into implementation tasks with acceptance criteria, evidence targets,
and validation posture. This plan does not supersede diagnosis history; it
operationalizes the diagnosed problem areas into tracked remediation work.

## Corrective Task Set

1. `TASK-CODE-BLOAT-REMEDIATION-001` - retire residual multi-shell and renderer
   branches.
2. `TASK-CODE-BLOAT-REMEDIATION-002` - remove legacy filesystem datum/bootstrap
   pathways and reduce snapshot bloat.
3. `TASK-CODE-BLOAT-REMEDIATION-003` - reduce Python import bloat and modularize
   runtime monoliths.
4. `TASK-CODE-BLOAT-REMEDIATION-004` - implement data I/O sizing controls with
   cache and stream boundaries.
5. `TASK-CODE-BLOAT-REMEDIATION-005` - decompose frontend bundles and enforce
   asset budgets.
6. `TASK-CODE-BLOAT-REMEDIATION-006` - consolidate duplicated normalization
   helpers under canonical contracts.
7. `TASK-CODE-BLOAT-REMEDIATION-007` - add bloat-regression guardrails for test
   overhead and CI budgets.
8. `TASK-CODE-BLOAT-REMEDIATION-008` - publish closure evidence and synchronize
   contextual/compatibility surfaces.

## Execution Rules

- Keep one canonical active plan and one canonical active report for this stream.
- Any split follow-on work that cannot be completed in this stream must be added
  as new stable task IDs in both task boards.
- Do not reopen `STREAM-CODE-BLOAT-DEEP-AUDIT`; retain it as completed planning
  evidence.
- If blocked, record blocker metadata on task board entries with impacted task
  IDs and next-unblocked guidance.

## Validation Posture

At minimum per remediation cycle, execute one unit suite, one integration suite,
and one contract/architecture suite from
`docs/plans/contextual_system_manifest.yaml` and record outcomes in the report.
