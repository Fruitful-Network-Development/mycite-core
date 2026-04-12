# Trusted-Tenant Shell Region Kinds

This document is the canonical wire contract summary for the current
trusted-tenant portal shell composition as emitted by the shared V2 runtime and
rendered by `v2_portal_shell.js`.

Authority:

- [v2-authority_stack.md](../plans/v2-authority_stack.md)
- [interface_surfaces.md](../ontology/interface_surfaces.md)
- `MyCiteV2/instances/_shared/runtime/tenant_portal_runtime.py`
- `MyCiteV2/instances/_shared/runtime/tenant_operational_status_runtime.py`
- `MyCiteV2/instances/_shared/runtime/tenant_audit_activity_runtime.py`
- `MyCiteV2/instances/_shared/runtime/tenant_profile_basics_write_runtime.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js`

## Workbench kinds emitted today

| Kind | Producer | Notes |
|---|---|---|
| `tenant_home_status` | trusted-tenant home runtime | Band 1 rollout/home summary surface |
| `operational_status` | operational-status runtime | fixed recent-window audit persistence summary |
| `audit_activity` | audit-activity runtime | bounded recent activity table/list |
| `profile_basics_write` | profile-basics runtime | bounded Band 2 trusted-tenant write form |

## Inspector kinds emitted today

| Kind | Producer | Notes |
|---|---|---|
| `tenant_profile_summary` | trusted-tenant home runtime | publication-backed tenant profile summary |
| `operational_status_summary` | operational-status runtime | audit persistence summary and slice posture |
| `audit_activity_summary` | audit-activity runtime | bounded recent-activity counts and latest timestamp |
| `profile_basics_write_summary` | profile-basics runtime | bounded write confirmation and recovery posture |

## Shared invariants

- Trusted-tenant shell composition is runtime-owned; the browser does not invent
  alternate slice navigation or region payloads.
- Workbench and inspector kinds are stable attachment surfaces. New tenant
  slices must add a runtime emitter and matching JS branch together.
- Lens or overlay behavior remains presentation-only. Trusted-tenant region
  payloads must still expose raw mediated state needed by the UI to render the
  chosen view.
