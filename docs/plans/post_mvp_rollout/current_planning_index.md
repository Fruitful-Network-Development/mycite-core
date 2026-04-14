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
| `AWS-CSM` family landing on `admin_band1.aws_read_only_surface` | implemented FND-first admin tool family | [../v2.3-tool_surface_packet/aws_csm.md](../v2.3-tool_surface_packet/aws_csm.md) |
| `admin_band5.cts_gis_read_only_surface` | finished FND-first admin tool deployment | [../v2.3-tool_surface_packet/cts_gis.md](../v2.3-tool_surface_packet/cts_gis.md) |
| `admin_band6.fnd_ebi_read_only_surface` | implemented FND-first admin tool | [../v2.3-tool_surface_packet/fnd_ebi.md](../v2.3-tool_surface_packet/fnd_ebi.md) |

The shared admin shell now uses the canonical root model:

- `System` is the default core root
- `Network` is the contract-first hosted/network read-model root
- `Utilities` is the canonical tool-bearing root
- tools are utility-sandbox surfaces, not peer shell roots
- the principal activity bar is visibly labeled and fixed to:
  `logo`, `NETWORK`, `SYSTEM`, `UTILITIES`, then the promoted tool family
  `AWS-CSM`
- `CTS-GIS` remains implemented but is reached through `Utilities`, not as a
  peer principal activity item
- `CTS-GIS` now uses the dominant interface panel as its Hanus lens surface,
  while the workbench stays mounted as secondary evidence and raw-inspection
  context
- `NETWORK` now renders `portal_instance`, `host_alias`,
  `external_service_binding`, `progeny_link`, and `p2p_contract` summaries
  while `host_alias_tool` runtime behavior remains held for a later pass
- `NETWORK` is read-only and contract-first; it is not the old V1
  contract-editor or profile-write surface

## Implemented V2.3 trusted-tenant surfaces

These client-facing rollout surfaces are implemented and should no longer be
read as the active near-term work queue.

| Surface | Current use | Implementation truth |
| --- | --- | --- |
| `band1.portal_home_tenant_status` | implemented trusted-tenant surface | [slice_registry/band1_portal_home_tenant_status.md](slice_registry/band1_portal_home_tenant_status.md) |
| `band1.operational_status_surface` | implemented trusted-tenant surface | [slice_registry/band1_operational_status_surface.md](slice_registry/band1_operational_status_surface.md) |
| `band1.audit_activity_visibility` | implemented trusted-tenant surface | [slice_registry/band1_audit_activity_visibility.md](slice_registry/band1_audit_activity_visibility.md) |
| `band2.profile_basics_write_surface` | implemented trusted-tenant surface | [slice_registry/band2_profile_basics_write_surface.md](slice_registry/band2_profile_basics_write_surface.md) |

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

## Active family-root tool planning

These are the current narrowed near-term family planning surfaces after the
canonical V2 closure and the implemented client/admin slices above.

| Surface | Queue posture | Why it is active now |
| --- | --- | --- |
| [../v2.3-tool_surface_packet/fnd_ebi.md](../v2.3-tool_surface_packet/fnd_ebi.md) | `implemented family root` | Canonical service/site operational visibility family with its first read-only admin slice now live. |
| [../v2.3-tool_surface_packet/cts_gis.md](../v2.3-tool_surface_packet/cts_gis.md) | `implemented family root` | Current admin CTS-GIS slice is a finished FND-first Hanus lens deployment; later spatial expansion stays under this family, but it is not the next immediate build target. |
| [../v2.3-tool_surface_packet/aws_csm.md](../v2.3-tool_surface_packet/aws_csm.md) | `implemented family root; next slice pending` | Current implementation truth for the live AWS-CSM family landing, newsletter operations, and subordinate AWS family surfaces. |

## Typed family plans not in the immediate build queue

These are canonical family-root docs, but they are not in the narrowed
near-term implementation queue.

| Surface | Current use | Notes |
| --- | --- | --- |
| [../v2.3-tool_surface_packet/agro_erp.md](../v2.3-tool_surface_packet/agro_erp.md) | clarified family root | Not held out, but not in the immediate narrowed queue. |
| [../v2.3-tool_surface_packet/fnd_dcm.md](../v2.3-tool_surface_packet/fnd_dcm.md) | typed family-root plan | New design/content family plan only. |
| [../v2.3-tool_surface_packet/paypal_ppm.md](../v2.3-tool_surface_packet/paypal_ppm.md) | typed family-root plan | Canonical PayPal family root replacing fragmented packet roots. |
| [../v2.3-tool_surface_packet/keycloak_sso.md](../v2.3-tool_surface_packet/keycloak_sso.md) | typed family-root plan | Clarified auth-provider family plan, not an immediate build target. |

## Held-out leftovers

These packet docs remain preserved but are outside the narrowed near-term set
until they receive family-level clarification.

| Surface | Queue posture | Notes |
| --- | --- | --- |
| [../v2.3-tool_surface_packet/data_tool.md](../v2.3-tool_surface_packet/data_tool.md) | `held out` | Not an approved family root. |
| [../v2.3-tool_surface_packet/fnd_provisioning.md](../v2.3-tool_surface_packet/fnd_provisioning.md) | `held out` | Preserve until a provisioning family brief exists. |
| [../v2.3-tool_surface_packet/operations.md](../v2.3-tool_surface_packet/operations.md) | `held out / legacy-isolation` | Not an approved family root. |
| [../../contracts/chronology_mediation_contract.md](../../contracts/chronology_mediation_contract.md) | `mediation contract` | Chronology is not an active tool packet item. |
| [../../contracts/host_alias_and_portal_instance_contract.md](../../contracts/host_alias_and_portal_instance_contract.md) | `contracts-first hosted work` | Hosted/progeny work now starts from entity contracts. |

## Supporting V2.3 tool packet

These documents do not replace the active slice queue above. They exist to make
tool follow-on work decision-complete before later tool implementation resumes.

| Surface | Current use | Notes |
| --- | --- | --- |
| [../v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../v2.3-tool_exposure_and_admin_activity_bar_alignment.md) | active foundational plan | Defines the proposed V2 `tool_exposure` gate and admin activity-bar contract. |
| [../../contracts/tool_exposure_and_admin_activity_bar_contract.md](../../contracts/tool_exposure_and_admin_activity_bar_contract.md) | current shell/tool contract truth | Documents the implemented root-shell + utility-tool activity-bar contract. |
| [../../contracts/shell_region_kinds.md](../../contracts/shell_region_kinds.md) | current shell region truth | Documents `active_service` as `system | network | utilities` and the current region kinds. |
| [../v2.3-tool_surface_packet/README.md](../v2.3-tool_surface_packet/README.md) | active per-tool planning packet | Index for one plan per current or legacy tool surface. |
| [../v2.3-tool_surface_packet/aws_csm.md](../v2.3-tool_surface_packet/aws_csm.md) | current implementation truth | Canonical implemented AWS-CSM family root and follow-on slice reference. |
| [../v2.3-tool_surface_packet/fnd_ebi.md](../v2.3-tool_surface_packet/fnd_ebi.md) | current implementation truth | Narrowed service/site operational visibility family with the first read-only slice implemented. |
| [../v2.3-tool_surface_packet/cts_gis.md](../v2.3-tool_surface_packet/cts_gis.md) | current implementation truth | Documents the finished FND-first admin CTS-GIS Hanus lens deployment and its rollout gate. |
| [../../contracts/tool_kind_and_portal_attachment_contract.md](../../contracts/tool_kind_and_portal_attachment_contract.md) | taxonomy truth | Documents `tool_kind`, root services, and shared portal capability declarations. |
| [../../contracts/network_operation_and_p2p_boundary.md](../../contracts/network_operation_and_p2p_boundary.md) | network sequencing truth | Documents the contracts-first hosted/network path. |
| [../../audits/v2_network_v1_to_v2_crosswalk_audit_2026-04-14.md](../../audits/v2_network_v1_to_v2_crosswalk_audit_2026-04-14.md) | network crosswalk audit | Maps V1 `NETWORK` ideas to the current V2 read-only root and records live runtime proof. |
| [../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md](../../audits/v2_tool_surface_and_legacy_tool_audit_2026-04-12.md) | supporting audit | Reconciles repo truth, live admin-shell truth, and legacy evidence. |

## Reading order for new work

1. Read [README.md](README.md).
2. Read [../../records/22-v1_retirement_closure.md](../../records/22-v1_retirement_closure.md).
3. Read [portal_rollout_bands.md](portal_rollout_bands.md).
4. Read [frozen_decisions_current_band.md](frozen_decisions_current_band.md).
5. Read [post_aws_tool_platform/README.md](post_aws_tool_platform/README.md) if the work changes shared post-AWS platform behavior.
6. Read the V2.3 tool packet documents when the work is about tool exposure,
   tool carry-forward, or legacy-tool classification.
7. Read the next active family-root doc in the sequence above.
8. Read the matching completion record only when you need historical implementation context.

## Archive rule

- `implemented_*` slice files are historical spec traces.
- completed cutover plans are record-first and should not be reopened as the default implementation path
- Completion truth for implemented work lives in `docs/records/`.
- New planning should start from the closure record and the reopened follow-on
  slice order, not from bridge-era cutover docs or implemented slice specs.
