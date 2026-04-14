# V3.4.4 V2 Portal UI Precision Refactor Audit

Date: 2026-04-14

## Summary

This audit records the precision-refactor baseline for the V2 portal browser
layer.

- V1 `base.html` remains the visual and ergonomic contract only.
- V2 `portal.html`, `shell_composition`, `shell_chrome`, and runtime envelopes
  remain the implementation authority.
- The refactor target is not a redesign. It is the browser delivery,
  hydration, renderer-ownership, and verification seam.

## Parity Matrix

| V1 shell element | Current V2 implementation file | keep / refactor / remove | owner | reason |
| --- | --- | --- | --- | --- |
| `ide-shell` | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | keep | template | The top-level shell wrapper already exists and should stay V2-owned. |
| `ide-menubar` | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | keep | template | Structure is already V1-recognizable and titles remain runtime-driven. |
| `ide-activitybar` | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | keep | template | The shell region exists and activity delivery remains server-issued. |
| `ide-logo` | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | refactor | template | Current V2 omits the dedicated V1-style logo node. |
| `ide-activitynav` | `portal.html` + `static/v2_portal_shell_core.js` | refactor | runtime | Truth is server-issued, but rendering still lives in shell core. |
| `ide-activityfooter` | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | keep | template | The region already exists and is acceptable as host metadata. |
| `ide-controlpanel` | `portal.html` + `static/v2_portal_shell_core.js` | refactor | runtime | The mount exists, but posture and rendering are still too browser-owned. |
| `ide-workbench` | `portal.html` + `static/v2_portal_shell_core.js` | refactor | runtime | The mount exists, but concrete rendering still lives in shell core. |
| `pagehead` | `portal.html` + `static/v2_portal_shell_core.js` | refactor | runtime | Visual parity is present, but title/subtitle updates are mixed with core rendering. |
| `viewport` | `portal.html` + renderer modules | keep | renderer | The region mount is correct and should remain a renderer concern. |
| `ide-inspector` | `portal.html` + `static/v2_portal_shell_core.js` | refactor | runtime | The mount exists, but open/closed truth must stay in `shell_chrome`. |
| `portalInspectorTransientMount` | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | refactor | template | Current V2 lacks the V1-style persistent/transient split. |
| template boot markers | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | refactor | template | Markers exist, but they still describe a compatibility-era boot chain. |
| shell script delivery path | `portal.html` + `static/v2_portal_shell.js` | refactor | template | The page still references a multi-script chain while `v2_portal_shell.js` is only a shim. |
| health check asset verification path | `app.py` + `tests/integration/test_v2_native_portal_host.py` | refactor | runtime | `/portal/healthz` still describes the stale compatibility artifact contract. |

## Fragility Audit

### Visual parity

- `portal.html` already contains the main V1-like shell regions, so the
  precision refactor is not a redesign.
- Two parity gaps remain in-repo:
  - the dedicated `.ide-logo` node is missing
  - the persistent/transient inspector mount split is missing

### Shell truth

- `shell_composition` and `shell_chrome` are the correct authority and must
  remain the only shell-truth interfaces.
- `portal.js` still reads `CONTROL_PANEL_OPEN_KEY` and `INSPECTOR_OPEN_KEY`,
  mutates `data-control-panel-collapsed` / `data-inspector-collapsed`, and
  therefore still owns shell posture locally under
  `data-portal-shell-driver="v2-composition"`.

### Renderer ownership

- `static/v2_portal_shell_core.js` remains too large and still owns concrete
  workbench and inspector rendering.
- Remaining workbench kinds still rendered in shell core:
  - `system_root`
  - `utilities_root`
  - `aws_csm_family_workbench`
  - `aws_csm_subsurface_workbench`
  - `home_summary`
  - `tenant_home_status`
  - `operational_status`
  - `audit_activity`
  - `profile_basics_write`
  - `tool_registry`
  - `datum_workbench`
  - `network_root`
  - `cts_gis_workbench`
  - `fnd_ebi_workbench`
- Remaining inspector kinds still rendered in shell core:
  - `datum_summary`
  - `cts_gis_interface_panel`
  - `cts_gis_summary`
  - `fnd_ebi_summary`
  - `network_summary`
  - `aws_csm_family_home`
  - `aws_read_only_surface`
  - `aws_tool_error`
  - `tenant_profile_summary`
  - `operational_status_summary`
  - `audit_activity_summary`
  - `profile_basics_write_form`
  - `narrow_write_form`
  - `csm_onboarding_form`

### Browser delivery and hydration risk

- `portal.html` currently loads six deferred scripts:
  - `portal.js`
  - `v2_portal_workbench_renderers.js`
  - `v2_portal_inspector_renderers.js`
  - `v2_portal_shell_core.js`
  - `v2_portal_shell.js`
  - `v2_portal_shell_watchdog.js`
- `/portal/static/v2_portal_shell.js` is only a compatibility wrapper and is
  not the real shipped shell asset.
- The watchdog currently observes side effects from shell core rather than the
  canonical bundle path.

### Deploy and static asset risk

- `/portal/healthz` currently reports `/portal/static/v2_portal_shell.js` as
  the bundle path even though the page still depends on the other directly
  loaded assets.
- Host/static tests currently assert the old multi-script template contract and
  therefore preserve the fragile boot chain.
- Health metadata still relies on the old compatibility-era marker story rather
  than the real entrypoint behavior.

### Browser smoke status

- `MyCiteV2/tests/integration/test_v2_portal_browser_smoke.py` already covers:
  - `/portal/system` hydration
  - `/portal/utilities/cts-gis` hydration
  - shell POST failure
  - internal shell bundle failure
- That suite still uses `skipUnless`, so missing Playwright silently skips the
  tests instead of failing repo completeness.
- There is no explicit render-dispatch fatal-path coverage yet.

### Remaining semantic gaps

- Control-panel posture is still client-owned in V2 driver mode.
- Fatal handling distinguishes bundle failure and shell POST failure, but not
  render-dispatch failure.
- `/portal/healthz` still validates the wrong artifact contract.

## Acceptance focus for the refactor

- `portal.html` must load only `portal.js` plus the canonical
  `/portal/static/v2_portal_shell.js`.
- `v2_portal_shell.js` must become the real canonical entrypoint.
- `v2_portal_shell_core.js` must become orchestration-only.
- Browser smoke must become required rather than silently skippable.
