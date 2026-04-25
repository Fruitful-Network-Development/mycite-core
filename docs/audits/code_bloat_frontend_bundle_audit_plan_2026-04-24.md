# Code Bloat Frontend Bundle Audit Plan

Date: 2026-04-24

Doc type: `audit-plan`
Normativity: `planning`
Lifecycle: `active`
Last reviewed: `2026-04-24`

## Registry

- Stream ID: `STREAM-CODE-BLOAT-DEEP-AUDIT`
- Compatibility initiative ID: `INIT-CODE-BLOAT-DEEP-AUDIT`
- Task ID: `TASK-CODE-BLOAT-AUDIT-005`
- Source report: `docs/audits/reports/code_bloat_diagnosis.md`
- Status: planning only; audit not executed.

## Audit Objective

Quantify static asset weight, parse/execute cost, route-level script necessity,
renderer dependency ownership, and deployment parity for portal frontend assets.

## Goes Further Than Diagnosis

The diagnosis flags monolithic JavaScript bundles. This plan requires measured
asset costs, critical-path classification, route-specific dependency maps, and
no-second-frontend-stack constraints before recommending bundle splitting.

## Evidence Targets

- `MyCiteV2/instances/_shared/portal_host/static/`
- `MyCiteV2/instances/_shared/portal_host/app.py`
- `docs/plans/one_shell_portal_refactor.md`
- `docs/contracts/portal_shell_contract.md`
- `docs/audits/reports/aws_csm_operational_recovery_audit_report_2026-04-24.md`

## Audit Procedure

1. Inventory JavaScript and CSS assets served by the portal host, including
   deployed snapshot parity where applicable.
2. Measure file size, compressed size if available, load order, and browser
   parse/execute impact for first-load and tool navigation paths.
3. Map frontend modules to shell core, shared utilities, CTS-GIS, AWS-CSM,
   workbench, and historical renderers.
4. Identify route-level lazy-loading or split candidates that preserve the
   single portal shell and existing static serving model.
5. Check cache headers, compression posture, and static asset invalidation.
6. Define smoke, accessibility, and route-regression evidence required for any
   frontend asset restructuring.

## Acceptance Criteria

- Audit output includes measured bundle/asset weights and critical-path status.
- Candidate splits are tied to route ownership and regression requirements.
- Findings report links to `TASK-CODE-BLOAT-AUDIT-005` and
  `STREAM-CODE-BLOAT-DEEP-AUDIT`.
