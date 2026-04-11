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
9. When the goal is operational replacement of the old admin portal or tool-bearing rollout, switch to [admin_first/README.md](admin_first/README.md).
10. After AWS read-only and AWS narrow-write are stable, use [post_aws_tool_platform/README.md](post_aws_tool_platform/README.md) before starting Maps or later tools.

## Operating rules

- No post-MVP implementation starts without a slice entry in [slice_registry/](slice_registry/).
- No slice becomes client-visible without passing [client_exposure_gates.md](client_exposure_gates.md).
- Runtime entrypoints must remain composition-only. See [runtime_entrypoints.md](runtime_entrypoints.md).
- Read-only rollout bands come before writable rollout bands.
- V1 workflow evidence may inform prioritization, but it may not define v2 structure.
- Admin-first operational replacement and tool-bearing rollout are governed by [admin_first/README.md](admin_first/README.md). That track nests under, and may not bypass, the global rollout bands.

## Current band status

- Current admin-first platform status: post-AWS tool platform stabilized.
- Completed admin-first slices: `Admin Band 0`, `admin_band1.aws_read_only_surface`, and `admin_band2.aws_narrow_write_surface`.
- Live `/portal` cutover status: Shape B bridge implemented for V2 admin shell reachability and configured live AWS profile mapping for FND/TFF. Use [post_aws_tool_platform/deployment_bridge_contract.md](post_aws_tool_platform/deployment_bridge_contract.md) and [post_aws_tool_platform/live_state_authority_and_mapping.md](post_aws_tool_platform/live_state_authority_and_mapping.md).
- Next allowed admin-first tool track: Maps, after reading [post_aws_tool_platform/README.md](post_aws_tool_platform/README.md) and [admin_first/maps_follow_on_surface.md](admin_first/maps_follow_on_surface.md).

## Preferred near-term sequence

1. Specify and approve [band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md) as the first client-facing orientation slice.
2. Build one read-only visibility slice next:
   - [band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md), or
   - [band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md)
   Choose one narrow slice, not both at once.
3. Keep [band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md) in specification-only status until at least one Band 1 slice is exposed safely.

Sandboxes, broad workflow parity, runtime flavor expansion, and AGRO-ERP-before-Maps remain outside this sequence.

## Initial slice registry entries

- [band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md)
- [band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md)
- [band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md)
- [band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md)
