# MOS System Surface Visualization Reflectivity Audit Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-22`

## Purpose

Audit whether `/portal/system` visualization remains state-machine reflective:
control panel as state-reaction contract, interface panel as mediation contract,
and workbench as datum-file representation. This plan is completed by
`docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md`.

## Scope

Runtime composition:

- `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py`
- `MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py`
- `MyCiteV2/instances/_shared/runtime/runtime_platform.py`

Host/static rendering:

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_system_workspace.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`

## Canonical Contract Links

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`

## Audit Questions

1. Does reducer-owned `SYSTEM` state map cleanly into region payloads?
2. Do workbench and interface roles remain distinct and additive?
3. Are renderer-unavailable states contract-diagnosable in payload terms?
4. Can stale or incomplete shell module loading create hidden drift from intent?

## Deliverables

- published report:
  `docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md`
- render-path matrix and mismatch diagnosis captured in that report
- deployment/build-id/cache/registration guardrails captured in code and tests

## Exit Criteria

- Report published root causes and mitigations for the named `/portal/system`
  reflectivity drift.
- Shell manifest/loader/renderer contracts now expose module-registration
  diagnostics for missing renderer paths.
- Verification checks now exist for manifest metadata, loader registry
  initialization, self-registration, and registry-backed SYSTEM dispatch.
