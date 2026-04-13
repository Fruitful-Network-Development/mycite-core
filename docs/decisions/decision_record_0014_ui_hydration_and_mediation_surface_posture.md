# Decision Record 0014: UI Hydration And Mediation Surface Posture

Date: 2026-04-13

## Status

Accepted.

## Context

The April 13 shell realignment pass corrected the shared shell away from
tool-owned layout rules, but it also flattened all tool surfaces back to a
workbench-first default. That contradicted the mediation-first intent for
`CTS-GIS`, left hydration failures visually ambiguous in the live portal, and
kept too much tool-specific rendering logic in one browser file.

## Decision

- shell truth remains server-owned
- browser JS remains a renderer and dispatcher only
- tool descriptors now carry `surface_posture`
- `CTS-GIS` is the first live `interface_panel_primary` tool
- workbench-primary remains the default for other current tools
- explicit collapse of an interface-panel-primary tool returns a
  shell-issued fallback workbench card instead of a client-guessed posture
- portal hydration must expose a DOM-visible boot state:
  `template | bundle_loaded | shell_posting | hydrated | fatal`
- the browser shell is split into ordered static scripts:
  - `v2_portal_workbench_renderers.js`
  - `v2_portal_inspector_renderers.js`
  - `v2_portal_shell_core.js`
  - `v2_portal_shell.js` as a compatibility wrapper
  - `v2_portal_shell_watchdog.js`

## Consequences

- `CTS-GIS` opens with the interface panel as the foreground mediation surface
  while keeping the workbench mounted as supporting context
- hydration failures become visible and testable instead of leaving template
  placeholders stranded
- new tool UI code extends renderer registries rather than expanding one
  monolithic browser switch
- trusted-tenant routes inherit the hydration hardening, but not the
  panel-primary posture unless a future tenant tool explicitly declares it
