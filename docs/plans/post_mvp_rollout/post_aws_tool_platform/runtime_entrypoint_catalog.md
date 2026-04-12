# Runtime Entrypoint Catalog

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

The canonical runtime entrypoint descriptor is `AdminRuntimeEntrypointDescriptor` in `instances/_shared/runtime/runtime_platform.py`.

## Current code catalog

- `admin.shell_entry`
- `admin.aws.read_only`
- `admin.aws.narrow_write`
- `admin.aws.csm_sandbox_read_only`
- `admin.aws.csm_onboarding`
- `admin.maps.read_only`

The MVP entrypoint remains valid, but post-AWS tool work uses the admin runtime
catalog. Trusted-tenant portal entrypoints are tracked separately in
[../runtime_entrypoints.md](../runtime_entrypoints.md).

## Required descriptor fields

Every admin runtime entrypoint descriptor must serialize:

- `schema`
- `entrypoint_id`
- `callable_path`
- `slice_id`
- `admin_band`
- `exposure_status`
- `read_write_posture`
- `launch_contract`
- `surface_pattern`
- `surface_schema`
- `required_configuration`

## Launch contracts

- `admin-shell-entry` is reserved for the deployable admin landing surface.
- `shell-owned-registry` is required for every tool-bearing entrypoint.

## Current meaning of the catalog

- `admin.aws.read_only` is the Band 1 trusted-tenant-safe read-only AWS surface.
- `admin.aws.narrow_write` is the Band 2 bounded-write AWS surface.
- `admin.aws.csm_sandbox_read_only` is the Band 3 internal sandbox-only
  read-only AWS-CSM surface.
- `admin.aws.csm_onboarding` is the Band 4 trusted-tenant-safe AWS-CSM
  onboarding surface.
- `admin.maps.read_only` is the Band 5 internal read-only Maps inspection
  surface built on authoritative datum documents plus bounded overlay
  projection.

## Runtime role

Runtime entrypoints may:

- normalize request envelopes
- resolve shell-owned launch decisions
- instantiate ports, adapters, and semantic owners
- compose response envelopes

Runtime entrypoints may not:

- define shell legality
- define tool descriptors
- define provider semantics
- define adapter policy
- bypass the shell-owned registry
