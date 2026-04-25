# Code Bloat Test Tooling Overhead Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-007`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Measure whether test fixtures, helper imports, suite organization, and missing
static-analysis gates are adding avoidable code weight or hiding future bloat
regressions.

## Goes Further Than Diagnosis

The diagnosis mentions testing/tooling overhead. This plan requires test import
timing, fixture duplication analysis, suite partitioning review, maintainability
metrics, and explicit bloat-regression gate design while preserving current
closure confidence.

## Evidence Targets

- `MyCiteV2/tests/`
- `docs/plans/contextual_system_manifest.yaml`
- `docs/plans/contextual_system_task_board.yaml`
- `docs/audits/reports/refinement_phase4_validation_report_2026-04-23.md`
- `docs/audits/reports/performance_weight_speed_report_2026-04-16.md`

## Audit Procedure

1. Measure test discovery/import time and identify slow helper or fixture import
   trees.
2. Inventory duplicated fixtures, large factories, stateful setup code, and
   expensive external-service stubs.
3. Classify suites by purpose: unit, integration, contract, architecture,
   performance, and migration/fixture support.
4. Identify static-analysis or maintainability metrics that should gate future
   bloat without blocking intentional audit/history retention.
5. Define candidate CI checks for import-time budgets, bundle-size budgets,
   module-size warnings, and duplicated-helper detection.
6. Specify evidence needed before changing any test structure that protects
   closure-critical behavior.

## Acceptance Criteria

- Audit output includes measured test/import overhead and fixture duplication
  findings.
- Proposed gates distinguish hard failures from advisory reports.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-007` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
