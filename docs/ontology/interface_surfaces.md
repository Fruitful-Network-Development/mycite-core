# Interface Surfaces

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

## Core terms

- `shell surface`: serialized shell state and legality owned by
  `packages/state_machine/`
- `mediation surface`: derived view or interaction rules for a subject
- `root_service`: a shell root such as `System`, `Network`, or `Utilities`
- `tool`: a shell-owned surface that attaches under a root and carries
  `tool_kind`
- `tool_kind`: one of `general_tool`, `service_tool`, or `host_alias_tool`
- `surface_posture`: one of `workbench_primary` or `interface_panel_primary`
- `sandbox boundary`: an orchestration boundary, not a domain owner

## Non-equivalences

- root service is not tool
- UI widget is not shell surface
- tool capability is not shell ownership
- service seam is not a generic folder
- mediation surface is not a tool by default

## Tool attachment rules

- tools attach to shell-defined context and mediation surfaces
- tools may not define alternate shell state
- tools may declare `surface_posture`, but the runtime remains the authority
  for how that posture becomes `foreground_shell_region` and inspector layout
- tools may emit tool-local `mediation_state` and server-issued navigation
  controls inside those shell-defined surfaces
- root services remain shell-owned and are not typed as tools
- chronology is currently mediation, not an active tool family

## Mediation-first surfaces

- `interface_panel_primary` means the tool mediates primarily through the
  interface panel while the workbench remains mounted as supporting context
- current live example: `CTS-GIS`
- the browser may render this posture, but it must not infer or mutate it on
  its own

## Sandboxes

- sandboxes mediate staged interaction between shell state, ports, adapters,
  and derived artifacts
- sandboxes do not redefine datum authority
