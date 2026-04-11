# Runtime Entrypoint Catalog

Authority: [../../authority_stack.md](../../authority_stack.md)

The canonical runtime entrypoint descriptor is `AdminRuntimeEntrypointDescriptor` in `instances/_shared/runtime/runtime_platform.py`.

## Current code catalog

- `admin.shell_entry`
- `admin.aws.read_only`
- `admin.aws.narrow_write`

The MVP entrypoint remains valid, but post-AWS tool work uses the admin runtime catalog.

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
