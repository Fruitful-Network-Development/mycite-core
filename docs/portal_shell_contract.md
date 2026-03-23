# Portal shell contract (SYSTEM)

## Regions

| Region | DOM / template | Owner |
|--------|----------------|-------|
| **Menu bar** | `base.html` → `.ide-menubar` | Shell |
| **Control panel** | `base.html` → `#portalControlPanel` | Shell layout plus page-local content |
| **Workbench** | `base.html` → `.ide-workbench` | Active module |
| **Details** | `base.html` → `#portalInspector` | Shell layout; modules mount persistent details content |

## Rules

1. SYSTEM must not expose duplicate anthology/resources tabs, body-level section tabs, or advertised Local Resources/Inheritance tabs.
2. The left page-local region is now called the **control panel** in copy and contracts.
3. The menubar keeps `Context`, `Details`, and `Theme` on one visible row.
4. SYSTEM details content lives in the shell inspector, not in a second center-column inspector.
5. The unified SYSTEM workbench uses one center surface with NIMM + AITAS state, not separate anthology/resources views.
6. Legacy SYSTEM query aliases may still resolve, but templates and active copy must not present them as current navigation.

## Implementation map

- `portals/.../templates/base.html`
- `portals/.../templates/services/system.html`
- `portals/.../templates/tools/partials/data_tool_shell.html`
- `portals/.../static/portal.css`
- `portals/.../static/portal.js`
- `portals/_shared/portal/ui/static/system_shell_runtime.js`
