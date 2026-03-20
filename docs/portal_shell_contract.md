# Portal shell contract (System page)

**Module content** (what each tab puts in workspace/inspector) is described in [`module_system_contract.md`](module_system_contract.md).

## Regions (frozen)

| Region | DOM / template | Owner |
|--------|----------------|--------|
| **Menu / title** | `base.html` → `ide-menubar`, `pagehead` (`page_title`, `page_subtitle`) | Shell only |
| **Left nav** | `ide-contextsidebar` (`{% block context_sidebar %}`) | Shell + section links only |
| **Center workspace** | `ide-workbench` → `section.viewport` → `{% block body %}` module root | Selected module only (data surface + controls) |
| **Right inspector** | `aside#portalInspector` → `#portalInspectorContent` (`{% block inspector_content %}`) + `#portalInspectorTransientMount` | Shell layout; modules mount persistent content in `inspector_content`; `PortalInspector.open` uses **transient** mount when a persistent system root is present |

## Rules

1. **Section selection** (Workbench / Local Resources / Inheritance) appears **only** in the context sidebar (`system.html` links). No duplicate `page-tabs` row in the body.
2. **Titles / instructional subtitles** for the System area are set via `page_title` / `page_subtitle` in the shell header, not repeated as module kicker/title prose inside the workspace.
3. **Inspector content never lives in the center grid.** System modules define persistent inspector nodes in `system.html` → `{% block inspector_content %}`. `data_tool.js` moves SAMRAS branch UI into `#systemInspectorPanelTxa`. Closing the inspector collapses the shell column (`portal.js`); it does not reflow inspector markup into the center.
4. **Workspace view modes** (anthology **table** vs **graph**) are mutually exclusive: only one of `#dtAnthologyGraph` / `#dtAnthologyLayers` regions is visible at a time (`data-layout-mode` + CSS). Default mode is **table**.
5. **Workbench submodes** (“Anthology” vs “SAMRAS sandbox”) are the only in-body tabs; they are not duplicates of section navigation.

## Implementation map

- `portals/.../templates/base.html` — `inspector_content` block, `portalInspectorTransientMount`, `PortalInspector` behavior.
- `portals/.../templates/services/system.html` — `inspector_content` per `current_tab`, `system-center-workspace` wrapper, no body tabs.
- `portals/.../templates/tools/partials/data_tool_shell.html` — center-only anthology + sandbox surfaces.
- `portal.js` — `__PORTAL_SHELL_INSPECTOR_DEFAULT_OPEN`, `PortalShell` API, transient vs persistent inspector content.
- `data_tool.js` — global `#dtAnthologyInspectorBody` / `#dtAnthologyInvMount`, TXA aside host, `syncSystemShellDataToolPanels`.
- `portal.css` — `.viewport--system`, `.system-shell-inspector`, table/graph exclusivity, two-column LR/inheritance center layouts.

## Tests

- `tests/test_system_page_composition.py`
- `tests/test_fnd_portal_shell_routes.py` (when Flask available)
