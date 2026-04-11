# Runtime Entrypoints

Authority: [../authority_stack.md](../authority_stack.md)

This file catalogs runtime entrypoints and constrains how new ones are added.

The code-level admin runtime entrypoint catalog is `instances/_shared/runtime/runtime_platform.py`.

## Policy

- Runtime entrypoints live under `instances/_shared/runtime/`.
- A runtime entrypoint is a top-level callable meant for host or test composition.
- One approved slice gets one public runtime entrypoint.
- Helper functions stay private inside the same file unless a later slice proves a shared need.
- No flavor-specific runtime composition is allowed in the current operating band.
- Runtime entrypoints may compose inward layers, but they may not define shell semantics, domain semantics, port contracts, or adapter rules.

## Current catalog

| Entrypoint id | Callable | Slice | Band | Exposure status | Inputs | Outputs |
|---|---|---|---|---|---|---|
| `mvp.shell_action_to_local_audit` | `instances._shared.runtime.mvp_runtime.run_shell_action_to_local_audit` | `Shell Action To Local Audit` | Band 0 | internal-only | serialized shell action payload, caller-supplied audit storage file | normalized subject, normalized shell verb, normalized shell state, persisted audit identifier, persisted audit timestamp |
| `admin.shell_entry` | `instances._shared.runtime.admin_runtime.run_admin_shell_entry` | `admin_band0.shell_entry` | `Admin Band 0 Internal Admin Replacement` | internal-only | serialized admin shell request payload, optional caller-supplied audit storage file | admin runtime envelope with normalized tenant scope, shell selection state, home/status or registry surface payload, and gated-slice error handling |
| `admin.aws.read_only` | `instances._shared.runtime.admin_aws_runtime.run_admin_aws_read_only` | `admin_band1.aws_read_only_surface` | `Admin Band 1 Trusted-Tenant AWS Read-Only` | trusted-tenant read-only | serialized AWS read-only request payload, caller-supplied AWS status snapshot file | admin runtime envelope with trusted-tenant-safe AWS operational visibility payload, explicit launch decision, and no write behavior |
| `admin.aws.narrow_write` | `instances._shared.runtime.admin_aws_runtime.run_admin_aws_narrow_write` | `admin_band2.aws_narrow_write_surface` | `Admin Band 2 Trusted-Tenant AWS Narrow Write` | trusted-tenant narrow write | serialized AWS narrow-write request payload, caller-supplied AWS status snapshot file, caller-supplied audit storage file | admin runtime envelope with bounded requested change, confirmed read-only AWS surface, persisted audit receipt, rollback reference, and explicit write status |
| `admin.aws.csm_sandbox_read_only` | `instances._shared.runtime.admin_aws_runtime.run_admin_aws_csm_sandbox_read_only` | `admin_band3.aws_csm_sandbox_surface` | `Admin Band 3 Internal AWS-CSM Sandbox` | internal sandbox read-only | same read-only request envelope as Band 1, **internal** `tenant_scope`, caller-supplied **sandbox** profile path (`MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE` on portal host) | admin runtime envelope with read-only surface and `active_surface_id` set to the sandbox slice; fails closed when path missing or invalid |

## Required catalog fields for future entrypoints

Every new entrypoint must be added here before implementation and must record:

- entrypoint id
- callable path
- slice id
- rollout band
- exposure status
- input contract
- output contract
- external configuration inputs
- owning tests

## Approval rule for new entrypoints

- A second public runtime entrypoint may not be added until its slice file exists in [slice_registry/](slice_registry/).
- A runtime entrypoint may not be added for an exposure band that is currently frozen.
- A runtime entrypoint may not be added just to compensate for missing lower-layer contracts.
- Every admin tool-bearing runtime entrypoint must be present in both `runtime_platform.py` and the shell-owned registry descriptor list.

## Forbidden runtime drift

- No unapproved or uncataloged tool wiring in shared runtime entrypoints during the current band.
- No sandbox orchestration in shared runtime entrypoints during the current band.
- No hidden read or write side channels.
- No instance-led directory math inside inward layers.
- No flavor copies of the same entrypoint.
