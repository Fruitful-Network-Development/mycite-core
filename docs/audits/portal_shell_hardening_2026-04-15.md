# Portal Shell Hardening Audit

This follow-up audit records the shell hardening pass that corrected the last unstable UI behaviors in the live one-shell portal.

## Findings

- The hydration flash was caused by the watchdog checking `__MYCITE_V2_SHELL_CORE_LOADED` and `__MYCITE_V2_SHELL_HYDRATED` before the core ever set those canonical globals.
- The shell template rendered two header regions: the top menubar and a second workbench pagehead with a duplicate theme selector.
- `inspector_collapsed` could report `false` even when runtime surfaces never explicitly opened the interface panel, because omitted `regions.inspector.visible` values were treated as visible by default.
- `focus_selection_panel` bypassed the standard control-panel section wrapper, which removed the expected padding around selection-panel content.
- Static shell assets were versioned inconsistently because the template, the loader, and the health report did not share one canonical asset manifest.

## Corrections

- The shell core now owns canonical boot globals for `core_loaded`, `hydrated`, and fatal state, and the watchdog only reports bundle-delivery failures.
- The top menubar is now the only shell header. The duplicate workbench pagehead and duplicate theme selector were removed.
- The left shell control is canonically `Control Panel` and the right shell rail is the `Interface Panel`.
- `inspector_collapsed` now defaults to `true` unless runtime explicitly projects `regions.inspector.visible=true` or the surface is tool-primary.
- `NETWORK` now keeps the interface panel collapsed until selected-record focus exists.
- `UTILITIES` now uses the same modular selection-panel shell shape without inventing sandbox/file/datum/object depth that the surface does not actually have.
- `focus_selection_panel` now renders inside the standard `.ide-controlpanel__section` wrapper so spacing is uniform with the rest of the shell.
- The host, template, loader, and health report now share one shell asset manifest, with `portal_build_id` cache-busting applied to `portal.css`, `portal.js`, `v2_portal_shell.js`, and every internal shell module.

## Expected Stable State

- No transient `Shell hydration failed` card during normal page load.
- One menubar header and one persistent theme selector.
- Root surfaces keep the interface panel closed by default unless the current focus explicitly projects interface detail.
- Tool-led surfaces remain interface-panel-led without collapsing into a blank page.
