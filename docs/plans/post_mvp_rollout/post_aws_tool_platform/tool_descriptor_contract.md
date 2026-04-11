# Tool Descriptor Contract

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

The canonical admin tool descriptor is `AdminToolRegistryEntry` in `packages/state_machine/hanus_shell/admin_shell.py`.

## Required descriptor fields

Every future admin tool descriptor must serialize these fields:

- `schema`: must be `mycite.v2.admin.tool_descriptor.v1`
- `tool_id`
- `label`
- `slice_id`
- `entrypoint_id`
- `admin_band`
- `exposure_status`
- `read_write_posture`
- `surface_pattern`
- `status_summary`
- `audience`
- `internal_only_reason`
- `audit_required`
- `read_after_write_required`
- `discovery_mode`
- `launch_contract`
- `default_posture`
- `launchable`

## Fixed descriptor policies

- `discovery_mode` is always `catalog-driven`.
- `launch_contract` is always `shell-owned-registry`.
- `default_posture` is always `deny-by-default`.
- `read_write_posture=read-only` requires `surface_pattern=read-only`.
- `read_write_posture=write` requires `surface_pattern=bounded-write`.
- writable descriptors must require both accepted-write audit and read-after-write confirmation.

## How future tools join the registry

A future tool may be added only by editing the shell-owned catalog after its slice file approves that tool.

Checklist:

- create or update the slice file in `docs/plans/post_mvp_rollout/slice_registry/`
- add exactly one `AdminToolRegistryEntry`
- add exactly one runtime entrypoint descriptor
- keep launch legality in `resolve_admin_tool_launch`
- add tests for descriptor shape, launch allow/deny, and runtime catalog consistency

## Forbidden descriptor drift

- no dynamic package scanning
- no tool-owned self-registration
- no provider route as descriptor source truth
- no mixed provider descriptor that hides multiple tools behind one entry
- no writable descriptor without audit and read-after-write confirmation
