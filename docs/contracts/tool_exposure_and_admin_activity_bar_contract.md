# Tool Exposure And Admin Activity Bar Contract

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This contract defines the forward V2 rule for admin tool visibility after the
post-AWS platform pass.

## Current V2 truth

- Shell registry owns tool legality, ordering, routing, slice identity,
  entrypoint identity, and audience rules.
- Current registry authority is
  `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`.
- Current runtime catalog authority is
  `MyCiteV2/instances/_shared/runtime/runtime_platform.py`.
- Current live V2 hosts do read `private/config.json.tool_exposure` for admin
  tool visibility and launch gating.
- The admin shell now uses a root-shell model:
  `System`, `Network`, and `Utilities` are canonical shell roots, while tools
  remain utility-sandbox surfaces launched under `Utilities`.

## Forward V2.3 contract

The forward model has two authorities, each with a different job.

### Authority 1: shell-owned registry

The shell registry remains canonical for:

- `tool_id`
- label
- slice order
- route and entrypoint identity
- audience and launch legality
- read-only vs bounded-write posture

Config may not redefine any of the items above.

### Authority 2: `private/config.json.tool_exposure`

`tool_exposure` is the new instance-level visibility gate.

Minimal shape:

```json
{
  "tool_exposure": {
    "aws": { "enabled": true },
    "aws_narrow_write": { "enabled": false }
  }
}
```

Rules:

- keys are V2 `tool_id` values
- `enabled=true` means the already-legal shell tool may be shown and launched
- `enabled=false` means the tool is hidden and blocked
- a missing key is treated the same as disabled
- config does not invent a tool that the shell registry does not know

## Dual-gate resolution

Every admin tool selection must pass both gates.

1. Resolve the shell-owned registry descriptor and audience rule.
2. Resolve `tool_exposure.<tool_id>.enabled`.
3. If both pass, the tool is visible and launchable.
4. If either fails, the tool is hidden and unlaunchable.

This is a `hide-and-block` contract, not a `show-gated` contract.

## Activity-bar contract

- Activity bar is shell-owned and compact, but not anonymous.
- Each principal item renders a shell-owned glyph plus a visible label.
- Activity bar order is shell-owned and fixed as:
  1. root logo to `System`
  2. `Network`
  3. `System`
  4. `Utilities`
  5. promoted tool families in shell-owned registry order
- Current principal tool-family set is intentionally narrow:
  - `AWS-CSM` is promoted
  - `Maps` remains implemented but is launched from `Utilities`, not pinned as a peer principal item
- Activity items are runtime-issued and must carry:
  - `icon_id`
  - `aria_label`
  - `nav_kind`
  - `shell_request`
- `nav_kind` is one of:
  - `root_logo`
  - `root_service`
  - `tool`
- The browser receives only the filtered set of principal tool items after the
  root items above.
- The browser must not merge config order, config labels, legacy route names,
  or client-invented icons into the rendered activity bar.
- Direct launch requests for a disabled tool must fail closed even if the tool
  exists in the shell registry.

## Four-panel shell invariant

- The admin shell keeps four stable modules:
  - activity bar
  - control panel
  - workbench
  - interface panel
- `composition_mode` may remain in the wire contract for semantic compatibility,
  but it must not hide the workbench or auto-promote the interface panel.
- The interface panel is secondary and collapsed by default; the workbench
  remains the primary content surface for both roots and tools.

## Canonical admin routes

- `/portal/system` is the default core root.
- `/portal/network` is the lightweight hosted/network root.
- `/portal/utilities` is the canonical tool-bearing root.
- `/portal/utilities/<tool_slug>` is the canonical deep-link pattern for utility
  tools.
- `/portal/system/<tool_slug>` and `/portal/system/tools` remain compatibility
  aliases.

## Legacy boundary

The following V1 concepts are not the forward V2 source of truth:

- `tools_configuration`
- `tools_configuration[].anchor`
- `mount_target`
- config-driven route naming
- config-driven tool ordering

Those remain migration evidence only.

## Required implementation consequences

When this contract is implemented in code:

- host config loading must parse `tool_exposure`
- admin runtime composition must filter tool visibility by dual gate
- admin runtime composition must emit root-shell activity items separately from
  utility tools
- launch resolution must enforce the same gate
- admin-shell health or audit surfaces should make the filtered tool set visible
  for debugging

## Forbidden drift

- no config-owned tool legality
- no dynamic package scanning
- no tool-owned self-registration
- no legacy `tools_configuration` revival as the active V2 contract
- no browser-owned fallback ordering for admin tools
