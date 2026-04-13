# Tool Exposure And Admin Activity Bar Contract

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This contract defines the forward V2 rule for shell-owned tool visibility.

## Current V2 truth

- shell registry owns tool legality, routing, order, audience, `tool_kind`,
  and `surface_posture`
- runtime entrypoint catalog must mirror the shell-owned tool contract
- `private/config.json.tool_exposure` is the instance visibility gate
- `System`, `Network`, and `Utilities` are root services, not tools

## Authority split

### Shell-owned registry

The shell registry remains canonical for:

- `tool_id`
- `tool_kind`
- `surface_posture`
- label
- slice and entrypoint identity
- audience and launch legality
- read/write posture
- shared portal capability declarations

Config may not redefine any of the above.

### `private/config.json.tool_exposure`

Minimal shape:

```json
{
  "tool_exposure": {
    "aws": { "enabled": true },
    "cts_gis": { "enabled": false }
  }
}
```

Rules:

- keys are shell-known V2 `tool_id` values
- missing keys are treated as disabled
- config may hide or enable a shell-legal tool
- config may not invent a new tool
- `calendar` is not a valid tool-exposure key in forward V2

## Activity-bar contract

- fixed order:
  1. root logo to `System`
  2. `Network`
  3. `System`
  4. `Utilities`
  5. promoted tool families in shell order
- current promoted tool family set is intentionally narrow:
  - `AWS-CSM` is promoted
  - `CTS-GIS` remains a utility tool under `Utilities`, even though its live
    tool posture is `interface_panel_primary`
- `nav_kind` remains `root_logo`, `root_service`, or `tool`
- tool activity items may carry `surface_posture`, but the activity bar still
  routes through shell-issued `shell_request` bodies instead of client-owned
  posture logic
- the browser must render only runtime-issued items and shell-issued
  `shell_request` bodies

## Canonical routes

- `/portal/system`
- `/portal/network`
- `/portal/utilities`
- `/portal/utilities/<tool_slug>`

Current CTS-GIS deep link:

- `/portal/utilities/cts-gis`

## Forbidden drift

- no `default_tool` vocabulary
- no config-owned tool legality
- no client-owned ordering or fallback registration
- no revival of `tools_configuration`
