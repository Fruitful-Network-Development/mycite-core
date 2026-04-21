# MOS System Surface Visualization Reflectivity Audit Plan

Date: 2026-04-21

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-21`

## Purpose

Audit whether `/portal/system` visualization remains state-machine reflective:
control panel as state-reaction contract, interface panel as mediation contract,
and workbench as datum-file representation. Include renderer fallback behavior
that can conceal contract-valid but UX-broken states.

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

- render-path matrix (`payload kind` -> `renderer` -> `fallback state`)
- mismatch list where payload contract is healthy but UX reflects unavailable state
- corrective guardrails for deployment/build-id/cache invalidation posture

## Exit Criteria

- Report publishes root causes and operational mitigations for renderer drift.
- At least one verification check is defined for every renderer-unavailable path.
