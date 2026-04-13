# Maps

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `Maps`\
Packet role: `family_root`\
Queue posture: `near-term candidate`\
Current live tool id: `maps`

## Current family truth

- Current code: V2 now has a shell-owned `maps` descriptor, runtime entrypoint
  `admin.maps.read_only`, direct host route
  `POST /portal/api/v2/admin/maps/read-only`, and shell render kinds
  `maps_workbench` plus `maps_summary`.
- Legacy evidence: V1 planning/docs and live FND sandbox source trees still
  exist for maps data and remain the historical evidence used to bound the V2
  carry-forward logic.
- Live presence: FND has `tool_exposure.maps.enabled=true` and the current V2
  admin shell exposes Maps there. TFF remains hidden and blocked. FND still has
  `private/utilities/tools/maps/` and `data/sandbox/maps/sources/`; TFF does
  not have a comparable sandbox.

This family root treats the current admin read-only Maps slice as the first
implemented slice of one spatial family, not as a standalone root tool.

## Core V2.3 position

`Maps` remains one spatial family.

It should not fragment into:

- admin maps
- public maps
- CTS
- coordinate inspector
- overlay browser

Those belong as later slices or audience views of the same family.

## Current implemented slice

The current implemented slice is the admin-first read-only Maps inspection
surface.

It keeps:

- authoritative datum documents as source truth
- raw datum visibility
- server-composed projection and overlays
- diagnostic handling for unresolved or invalid values

## Next slice under this family

The next family slice is a portal/default-app Maps expansion.

That slice should:

- preserve server-composed projection
- preserve diagnostics and raw authority underneath overlays
- remain datum-authority-first
- avoid inventing a second spatial family or second spatial truth model

## Do not carry forward

Do not carry forward:

- alternate root names like `CTS`
- browser-owned projection logic
- silent handling of invalid coordinates
- config-owned launch rules or routing semantics
