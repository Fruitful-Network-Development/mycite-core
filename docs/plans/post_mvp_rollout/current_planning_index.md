# Current Planning Index

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Use this file before reading the rest of `post_mvp_rollout/`.

Its job is to separate:

- active planning that is still unimplemented
- historical slice specs that are already implemented and should now be read
  through completion records

## Canonical closure record

The canonical V2 closure sequence is complete. Use
[../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md)
for the formal statement that V1 is retained only as historical evidence and
that follow-on planning may resume from Band 1.

## Record-only implemented slices

These slice specs are no longer the active planning entrypoint. Keep them only
as slice-definition history.

| Slice or surface | Current use | Completion record |
| --- | --- | --- |
| `admin_band0.home_status` | record-only | [../../records/10-admin_band_0_internal_admin_replacement.md](../../records/10-admin_band_0_internal_admin_replacement.md) |
| `admin_band0.shell_entry` | record-only | [../../records/10-admin_band_0_internal_admin_replacement.md](../../records/10-admin_band_0_internal_admin_replacement.md) |
| `admin_band0.tool_registry` | record-only | [../../records/10-admin_band_0_internal_admin_replacement.md](../../records/10-admin_band_0_internal_admin_replacement.md) |
| `admin_band0.v2_deployment_bridge` | record-only | [../../records/15-cut_over.md](../../records/15-cut_over.md) |
| `admin_band1.aws_read_only_surface` | record-only | [../../records/11-admin_band_1_aws_read_only_surface.md](../../records/11-admin_band_1_aws_read_only_surface.md) |
| `admin_band2.aws_narrow_write_surface` | record-only | [../../records/12-admin_band_2_aws_narrow_write_surface.md](../../records/12-admin_band_2_aws_narrow_write_surface.md) |
| `admin_band3.aws_csm_sandbox_surface` | record-only | [../../records/T-008-implementation.md](../../records/T-008-implementation.md) |
| `admin_band4.aws_csm_onboarding_surface` | record-only | [../../records/T-010-implementation.md](../../records/T-010-implementation.md) |

## Implemented V2.3 admin tool surfaces

These are implemented through the V2.3 tool packet and current repo/runtime
truth, not through the older slice-registry sequence above.

| Surface | Current use | Implementation truth |
| --- | --- | --- |
| `admin_band5.maps_read_only_surface` | implemented FND-first admin tool | [../v2.3-tool_surface_packet/maps.md](../v2.3-tool_surface_packet/maps.md) |

## Record-only cutover plans

These cutover documents describe completed bridge-era or native-cutover work.
They are useful historical evidence, but they are not the current work queue.

| Surface | Current use | Completion record |
| --- | --- | --- |
| [post_aws_tool_platform/deployment_bridge_contract.md](post_aws_tool_platform/deployment_bridge_contract.md) | historical bridge design | [../../records/15-cut_over.md](../../records/15-cut_over.md) |
| [post_aws_tool_platform/cutover_execution_sequence.md](post_aws_tool_platform/cutover_execution_sequence.md) | historical cutover sequence | [../../records/15-cut_over.md](../../records/15-cut_over.md), [../../records/16-v2_native_portal_cutover.md](../../records/16-v2_native_portal_cutover.md) |
| [post_aws_tool_platform/v2_admin_cutover_readiness.md](post_aws_tool_platform/v2_admin_cutover_readiness.md) | posture reference, not work queue | [../../records/16-v2_native_portal_cutover.md](../../records/16-v2_native_portal_cutover.md) |

## Closed canonicalization sequence

These surfaces are no longer the active work queue. They remain as posture,
ledger, and gate evidence behind the closure record.

| Surface | Current use | Closure evidence |
| --- | --- | --- |
| [post_aws_tool_platform/v2_native_cutover_hardening.md](post_aws_tool_platform/v2_native_cutover_hardening.md) | completed closure packet | [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md) |
| [post_aws_tool_platform/v1_retirement_execution_ledger.md](post_aws_tool_platform/v1_retirement_execution_ledger.md) | resolved execution ledger | [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md) |
| [../phases/11_cleanup_and_v1_retirement_review.md](../phases/11_cleanup_and_v1_retirement_review.md) | closed phase gate | [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md) |
| [post_aws_tool_platform/README.md](post_aws_tool_platform/README.md) | platform posture and historical rules | [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md) |

## Active post-MVP planning

These are the current unimplemented planning surfaces after canonical V2
closure.

| Surface | Status | Why it is now active or sequenced |
| --- | --- | --- |
| [slice_registry/band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md) | `first active slice` | First client-facing orientation slice now that canonical V2 and V1 retirement closure are complete. |
| [slice_registry/band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md) | `second active slice` | Chosen as the next read-only visibility slice after the home surface. |
| [slice_registry/band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md) | `third active slice` | Still sequenced after the operational status surface rather than treated as an equal alternate path. |
| [slice_registry/band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md) | `fourth active slice` | Writable follow-on only after the three Band 1 read-only slices are stable. |
| [admin_first/agro_erp_follow_on_surface.md](admin_first/agro_erp_follow_on_surface.md) | `after implemented Maps baseline` | Still follows the Maps carry-forward and remains deferred. |

## Supporting V2.3 tool packet

These documents do not replace the active slice queue above. They exist to make
tool follow-on work decision-complete before later tool implementation resumes.

| Surface | Current use | Notes |
| --- | --- | --- |
| [../v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../v2.3-tool_exposure_and_admin_activity_bar_alignment.md) | active foundational plan | Defines the proposed V2 `tool_exposure` gate and admin activity-bar contract. |
| [../v2.3-tool_surface_packet/README.md](../v2.3-tool_surface_packet/README.md) | active per-tool planning packet | Index for one plan per current or legacy tool surface. |
| [../v2.3-tool_surface_packet/maps.md](../v2.3-tool_surface_packet/maps.md) | current implementation truth | Documents the implemented admin Maps read-only slice and its FND-first rollout. |
| [../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md](../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md) | supporting audit | Reconciles repo truth, live admin-shell truth, and legacy evidence. |

## Reading order for new work

1. Read [README.md](README.md).
2. Read [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md).
3. Read [portal_rollout_bands.md](portal_rollout_bands.md).
4. Read [frozen_decisions_current_band.md](frozen_decisions_current_band.md).
5. Read [post_aws_tool_platform/README.md](post_aws_tool_platform/README.md) if the work changes shared post-AWS platform behavior.
6. Read the V2.3 tool packet documents when the work is about tool exposure,
   tool carry-forward, or legacy-tool classification.
7. Read the next active slice file in the sequence above.
8. Read the matching completion record only when you need historical implementation context.

## Archive rule

- `implemented_*` slice files are historical spec traces.
- completed cutover plans are record-first and should not be reopened as the default implementation path
- Completion truth for implemented work lives in `docs/records/`.
- New planning should start from the closure record and the reopened follow-on
  slice order, not from bridge-era cutover docs or implemented slice specs.
