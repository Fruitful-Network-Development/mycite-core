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
- root services remain shell-owned and are not typed as tools
- chronology is currently mediation, not an active tool family

## Sandboxes

- sandboxes mediate staged interaction between shell state, ports, adapters,
  and derived artifacts
- sandboxes do not redefine datum authority
