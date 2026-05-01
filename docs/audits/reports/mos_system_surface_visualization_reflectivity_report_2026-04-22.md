# MOS System Surface Visualization Reflectivity Report

Date: 2026-04-22

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-22`

## Purpose

Close the named `/portal/system` render-reflectivity drift from
`mos_runtime_authority_and_access_reality_report_2026-04-21.md` by proving that
the bundled shell now carries an explicit module-registration contract for the
SYSTEM workbench renderer and by making missing-registration states
contract-diagnosable.

## Scope

- `MyCiteV2/instances/_shared/portal_host/app.py`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_watchdog.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_system_workspace.js`
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_tool_surface_adapter.js`
- `MyCiteV2/tests/architecture/test_portal_one_shell_boundaries.py`
- `MyCiteV2/tests/integration/test_portal_host_one_shell.py`

## Findings

### 1) The shell asset manifest now publishes renderer contracts, not just files

`build_shell_asset_manifest()` now emits ordered `shell_modules` entries with:

- `module_id`
- canonical asset path/url metadata
- `exports[]` contract metadata with expected global names and required callables

The embedded `portal.html` manifest remains the only source of truth, and
`/portal/healthz` exposes the same expanded contract.

Status: `closed`

### 2) The shell loader now owns a first-class module registry and boot diagnostics

`v2_portal_shell.js` now initializes a shared runtime registry plus
`window.__MYCITE_V2_REGISTER_SHELL_MODULE(...)`,
`window.__MYCITE_V2_GET_SHELL_MODULE_DIAGNOSTICS(...)`, and
`window.__MYCITE_V2_RESOLVE_SHELL_MODULE_EXPORT(...)`.

The registry records:

- expected modules from the manifest
- actual script load order
- successful registrations
- invalid registrations
- current boot stage

Status: `closed`

### 3) Every bundled shell module with runtime behavior now self-registers

The following modules now register themselves immediately after assigning their
public globals:

- region renderers
- tool-surface adapter
- AWS workspace/inspector renderer module
- SYSTEM workspace renderer
- NETWORK workspace/inspector renderer module
- workbench renderer set
- inspector renderer set
- shell core
- shell watchdog

Status: `closed`

### 4) `/portal/system` now resolves the SYSTEM renderer through the registry contract

`v2_portal_workbench_renderers.js` no longer treats
`window.PortalSystemWorkspaceRenderer` as sufficient proof of health. It now
resolves the SYSTEM renderer through the shared registry contract.

If the module is missing or malformed, the unsupported workbench state now names:

- `module_id=system_workspace`
- `expected_global=PortalSystemWorkspaceRenderer`
- `expected_callable=render`
- current boot stage
- loaded script order
- registered module set
- invalid registration messages
- contract failures

This closes the prior generic symptom:
`The system workspace renderer is unavailable.`

Status: `closed`

### 5) Fatal taxonomy now distinguishes bundle delivery from registration failure

The shell still reports:

- `asset_manifest_missing` when the manifest is absent
- `bundle_not_loaded` when internal scripts fail to load or execute

It now also reports:

- `module_registration_missing` when the bundle loads but required registered
  shell exports are missing or non-callable

Status: `closed`

## Verification

- `python3 -m unittest MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
- `python3 -m unittest MyCiteV2.tests.integration.test_portal_host_one_shell`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
- `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`

## Result

The named `/portal/system` render-reflectivity drift is closed. The deployed
one-shell host now publishes a canonical shell-module contract, the SYSTEM
renderer is resolved through that contract, and missing-registration states are
reported with explicit module-level diagnostics instead of a generic
unavailable-renderer message.
