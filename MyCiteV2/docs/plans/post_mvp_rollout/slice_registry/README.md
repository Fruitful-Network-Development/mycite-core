# Slice Registry

Authority: [../../authority_stack.md](../../authority_stack.md)

This registry is the mandatory staging surface for post-MVP slice work.

## Registry rule

- No new post-MVP implementation starts without a slice file in this directory.
- Slice files must use [slice_template.md](slice_template.md).
- Slice files are the narrowest approved planning unit for future agent work.

## Required slice statuses

- `candidate`
- `approved_for_build`
- `implemented_internal`
- `client_visible`
- `frozen`
- `superseded`

## Naming rule

- Use `band<number>_<short_slice_name>.md`.
- The filename should describe the rollout band and the user-facing slice.

## Required process

1. Create or update the slice file.
2. Assign rollout band and exposure status.
3. Name owning layers, required ports, required adapters, and runtime composition.
4. Link the needed tests and [../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md).
5. Update [../runtime_entrypoints.md](../runtime_entrypoints.md) before adding a new runtime entrypoint.
6. Pass [../client_exposure_gates.md](../client_exposure_gates.md) before requesting client exposure.

## Minimum slice packet

Every slice file must let a future agent answer, without prior chat context:

- what the user-facing surface is
- why the slice belongs in its rollout band
- which layers own semantics, contracts, adapter behavior, and runtime composition
- which tests must pass before exposure
- what remains explicitly out of scope
- which v1 areas are evidence only or drift warnings

## Initial entries

- [band1_portal_home_tenant_status.md](band1_portal_home_tenant_status.md)
- [band1_audit_activity_visibility.md](band1_audit_activity_visibility.md)
- [band1_operational_status_surface.md](band1_operational_status_surface.md)
- [band2_profile_basics_write_surface.md](band2_profile_basics_write_surface.md)
