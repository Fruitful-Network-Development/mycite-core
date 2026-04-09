# Post-MVP Rollout

Authority: [../authority_stack.md](../authority_stack.md)

This subtree is the post-MVP operating surface for building the rest of MyCiteV2 into a client-stable portal without reintroducing v1 drift.

Use it after the MVP is proven and before any new client-visible slice is specified or implemented.

## Use order

1. Read [portal_rollout_bands.md](portal_rollout_bands.md).
2. Read [frozen_decisions_current_band.md](frozen_decisions_current_band.md).
3. Read [v1_parity_ledger.md](v1_parity_ledger.md).
4. Read [slice_registry/README.md](slice_registry/README.md).
5. Read [client_exposure_gates.md](client_exposure_gates.md).
6. Read [runtime_entrypoints.md](runtime_entrypoints.md).
7. Read [port_adapter_ownership_matrix.md](port_adapter_ownership_matrix.md).
8. Use [agent_prompt_templates.md](agent_prompt_templates.md) when handing work to future agents.

## Operating rules

- No post-MVP implementation starts without a slice entry in [slice_registry/](slice_registry/).
- No slice becomes client-visible without passing [client_exposure_gates.md](client_exposure_gates.md).
- Runtime entrypoints must remain composition-only. See [runtime_entrypoints.md](runtime_entrypoints.md).
- Read-only rollout bands come before writable rollout bands.
- V1 workflow evidence may inform prioritization, but it may not define v2 structure.

## Current band status

- Current exposure band: `Band 0 Internal Only`.
- Current build target: `Band 1 Trusted-Tenant Read-Only`.
- Writable slice work may be specified now, but it is not approved for implementation until Band 1 slices are stable.

## Preferred near-term sequence

1. Specify and approve [band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md) as the first client-facing orientation slice.
2. Build one read-only visibility slice next:
   - [band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md), or
   - [band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md)
   Choose one narrow slice, not both at once.
3. Keep [band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md) in specification-only status until at least one Band 1 slice is exposed safely.

Tools, sandboxes, broad workflow parity, and runtime flavor expansion stay outside this sequence.

## Initial slice registry entries

- [band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md)
- [band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md)
- [band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md)
- [band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md)
