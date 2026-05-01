# Code Bloat Python Import Modularity Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-003`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Measure Python startup/import cost, identify monolithic module pressure, and
separate contract-required eager imports from heavy dependencies that can be
deferred or isolated by domain.

## Goes Further Than Diagnosis

The diagnosis flags heavy imports and large modules. This plan requires
repeatable import-time profiling, module ownership mapping, line/function
complexity thresholds, and side-effect checks before recommending local imports
or module splits.

## Evidence Targets

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_aws_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_cts_gis_runtime.py`
- `MyCiteV2/packages/`
- `docs/contracts/tool_operating_contract.md`

## Audit Procedure

1. Run an import-time profile for portal host startup and major runtime modules.
2. Build a top-import-cost table with module, parent importer, elapsed time, and
   suspected domain owner.
3. Inventory modules above agreed size and complexity thresholds, including
   module-level initialization or file/network access.
4. Classify heavy imports as contract-required eager, safe to defer, unsafe to
   defer, or needing an adapter boundary.
5. Identify module-split candidates with proposed ownership boundaries and
   compatibility risks.
6. Define regression checks for import time and route initialization behavior.

## Acceptance Criteria

- Audit output includes raw import-time evidence and a reviewed candidate list.
- Recommendations distinguish lazy import, adapter extraction, and no-change
  decisions with rationale.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-003` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
