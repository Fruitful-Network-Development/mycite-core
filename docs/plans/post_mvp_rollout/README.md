# Post-MVP Rollout

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

This subtree is the post-MVP operating surface for building the rest of MyCiteV2 into a client-stable portal without reintroducing v1 drift.

Use it after the MVP is proven and before any new client-visible slice is specified or implemented.

## Use order

1. Read [current_planning_index.md](current_planning_index.md).
2. Read [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md).
3. Read [portal_rollout_bands.md](portal_rollout_bands.md).
4. Read [frozen_decisions_current_band.md](frozen_decisions_current_band.md).
5. Read [slice_registry/README.md](slice_registry/README.md).
6. Read [client_exposure_gates.md](client_exposure_gates.md).
7. Read [runtime_entrypoints.md](runtime_entrypoints.md).
8. Read [port_adapter_ownership_matrix.md](port_adapter_ownership_matrix.md).
9. Use [agent_prompt_templates.md](agent_prompt_templates.md) when handing work to future agents.
10. When the work is about the shared post-AWS platform for later tools, read [post_aws_tool_platform/README.md](post_aws_tool_platform/README.md).
11. When the work is about admin-first follow-on sequencing, read [admin_first/README.md](admin_first/README.md).
12. When the work is about V2.3-era tool exposure gating or legacy tool carry-forward, read [../v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../v2.3-tool_exposure_and_admin_activity_bar_alignment.md) and [../v2.3-tool_surface_packet/README.md](../v2.3-tool_surface_packet/README.md).

## Operating rules

- No post-MVP implementation starts without a slice entry in [slice_registry/](slice_registry/).
- No slice becomes client-visible without passing [client_exposure_gates.md](client_exposure_gates.md).
- Runtime entrypoints must remain composition-only. See [runtime_entrypoints.md](runtime_entrypoints.md).
- Implemented slice specs are record-only planning history. Use [../../records/README.md](../../records/README.md) for completion evidence.
- Read-only rollout bands come before writable rollout bands.
- V1 workflow evidence may inform prioritization, but it may not define v2 structure.
- Admin-first operational replacement and tool-bearing rollout are governed by [admin_first/README.md](admin_first/README.md). That track nests under, and may not bypass, the global rollout bands.
- New follow-on work still respects the ordered rollout sequence; closure of the
  retirement gate does not make later slices co-equal with the first reopened
  Band 1 slice.

## Current band status

- Current admin-first platform status: post-AWS tool platform stabilized.
- Completed admin-first slices: `Admin Band 0`, `admin_band1.aws_read_only_surface`, `admin_band2.aws_narrow_write_surface`, `admin_band3.aws_csm_sandbox_surface`, `admin_band4.aws_csm_onboarding_surface`, and `admin_band5.maps_read_only_surface` (FND-first rollout).
- Implemented trusted-tenant rollout slices: `band1.portal_home_tenant_status`, `band1.operational_status_surface`, `band1.audit_activity_visibility`, and `band2.profile_basics_write_surface`.
- Live `/portal` cutover status: V2-native portal host deployed for FND and TFF. The earlier Shape B bridge is retained only as historical cutover evidence; see [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md) for the formal closure statement.
- Canonical live AWS mapping status: current and active through [post_aws_tool_platform/live_state_authority_and_mapping.md](post_aws_tool_platform/live_state_authority_and_mapping.md).
- Current expansion posture: follow-on slices may resume from the reopened Band
  1 sequence documented in [current_planning_index.md](current_planning_index.md), but the narrowed family-root tool queue now treats `AWS-CSM` as the next actual build target, with `FND-EBI` and `Maps` as the other near-term candidates.
- Tool follow-on work now also uses the V2.3 audit and packet documents when
  deciding whether a legacy tool becomes a V2 tool, stays isolated, or is
  retired.

## Preferred near-term sequence

1. Use [../v2.3-tool_surface_packet/aws_csm.md](../v2.3-tool_surface_packet/aws_csm.md) as the next actual family-root build target.
2. Keep [../v2.3-tool_surface_packet/fnd_ebi.md](../v2.3-tool_surface_packet/fnd_ebi.md) as the other narrowed near-term candidate.
3. Keep [../v2.3-tool_surface_packet/maps.md](../v2.3-tool_surface_packet/maps.md) as the remaining near-term candidate, with portal/default-app expansion as the next family slice.
4. Treat [../v2.3-tool_surface_packet/fnd_dcm.md](../v2.3-tool_surface_packet/fnd_dcm.md), [../v2.3-tool_surface_packet/calendar.md](../v2.3-tool_surface_packet/calendar.md), [../v2.3-tool_surface_packet/paypal_ppm.md](../v2.3-tool_surface_packet/paypal_ppm.md), and [../v2.3-tool_surface_packet/keycloak_sso.md](../v2.3-tool_surface_packet/keycloak_sso.md) as typed family plans, not immediate build targets.

`fnd_provisioning`, `tenant_progeny_profiles`, `data_tool`, and `operations`
remain outside this narrowed near-term set until they receive the same
family-level clarification.

## Historical implemented slice specs

- [band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md)
- [band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md)
- [band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md)
- [band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md)
