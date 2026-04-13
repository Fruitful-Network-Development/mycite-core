# Tool Kind And Portal Attachment Contract

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This contract defines how V2 distinguishes shell roots from tools and how
shell-owned tools are typed.

## Root rule

- `System`, `Network`, and `Utilities` are `root_service` shell items.
- Root services are not tools.
- Root services may have tabs and shell surfaces, but they do not carry
  `tool_id` or `tool_kind`.

## Tool descriptor rule

Every shell-owned tool descriptor and tool runtime entrypoint must carry:

- `tool_id`
- `tool_kind`
- `slice_id`
- `entrypoint_id`
- `read_write_posture`
- optional `shared_portal_capabilities`

`tool_kind` must be one of:

- `general_tool`
- `service_tool`
- `host_alias_tool`

`default_tool` is forbidden vocabulary.

## Meaning Of Each Tool Kind

- `general_tool`: a tool that plugs into shell surfaces without owning an
  external provider family
- `service_tool`: a tool that composes provider-facing or shared service
  capabilities through shell-owned legality and runtime composition
- `host_alias_tool`: a future hosted/network tool family that composes portal
  instance, alias, and provider bindings after the hosted/network contracts are
  approved

## Shared Portal Capabilities

`shared_portal_capabilities` is optional and declarative. It may be empty.

Examples:

- `external_service_binding`
- `sandbox_projection`
- `datum_recognition`
- `spatial_projection`

These declarations do not grant authority by themselves. They only state which
shared portal capabilities a shell-owned tool consumes.

## Current Live Mapping

| Tool | Current `tool_kind` | Notes |
| --- | --- | --- |
| `aws` | `service_tool` | family landing for AWS-CSM |
| `aws_narrow_write` | `service_tool` | bounded write subordinate slice |
| `aws_csm_sandbox` | `service_tool` | internal sandbox projection |
| `aws_csm_onboarding` | `service_tool` | bounded onboarding orchestration |
| `cts_gis` | `general_tool` | spatial read-only utility tool under `Utilities` |
| `fnd_ebi` | `service_tool` | hosted site visibility family under `Utilities` |

## Immediate implementation rule

- add or update tool docs only after the shell registry and runtime entrypoint
  catalog agree on `tool_kind`
- do not introduce `host_alias_tool` runtime behavior until the hosted/network
  contracts land
