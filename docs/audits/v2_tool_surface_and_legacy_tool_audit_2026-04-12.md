# V2 Tool Surface And Legacy Tool Audit

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

Date: `2026-04-12`

## Purpose

This audit reconciles four surfaces that had started to drift apart:

- current V2 shell and runtime code
- live deployed admin-shell behavior on FND and TFF
- legacy V1 tool packages, portal tool surfaces, and state layouts
- post-AWS and V2.3 planning/docs that now need a stable forward tool model

If this audit conflicts with the authority stack or current repo code, the
audit loses.

## Repo truth

Current V2 tool legality is shell-owned and catalog-driven.

- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` is the canonical
  tool registry and launch-legality source.
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py` composes the admin shell
  and activity-bar payload from shell-owned catalog entries.
- `MyCiteV2/instances/_shared/runtime/runtime_platform.py` is the canonical
  runtime-entrypoint catalog.
- No current V2 code path was found that reads `private/config.json` to decide
  admin activity-bar visibility or tool launch legality.

Current registry-backed admin tools in code:

| V2 tool id | Slice id | Entrypoint id | Audience | Current status |
| --- | --- | --- | --- | --- |
| `aws` | `admin_band1.aws_read_only_surface` | `admin.aws.read_only` | `trusted-tenant-admin` | current V2 |
| `aws_narrow_write` | `admin_band2.aws_narrow_write_surface` | `admin.aws.narrow_write` | `trusted-tenant-admin` | current V2 |
| `aws_csm_sandbox` | `admin_band3.aws_csm_sandbox_surface` | `admin.aws.csm_sandbox_read_only` | `internal-admin` | current V2 |
| `aws_csm_onboarding` | `admin_band4.aws_csm_onboarding_surface` | `admin.aws.csm_onboarding` | `trusted-tenant-admin` | current V2 |

## Live deployed truth

Loopback checks against `127.0.0.1:6101` and `127.0.0.1:6203` show:

- both live hosts report `portal_build_id: 0c34efd`
- both hosts report `host_shape: v2_native`
- both hosts expose the trusted-tenant route contract for `/portal/home`,
  `/portal/status`, `/portal/activity`, and `/portal/profile-basics`
- both hosts also answer `POST /portal/api/v2/admin/shell`

Live admin-shell registry output on both FND and TFF currently includes:

- `aws`
- `aws_narrow_write`
- `aws_csm_sandbox`
- `aws_csm_onboarding`

This means the live V2 admin shell already exposes tool slices by shell
registry. The missing piece is not registry wiring; it is a V2-native
instance-level visibility gate and the documentation to match it.

## State and utility truth

Legacy-style state and utility roots still exist under
`/srv/mycite-state/instances/fnd/`.

Observed FND utility roots:

- `private/utilities/tools/aws-csm/`
- `private/utilities/tools/fnd-ebi/`
- `private/utilities/tools/keycloak-sso/`
- `private/utilities/tools/maps/`
- `private/utilities/tools/agro-erp/`
- `private/utilities/tools/newsletter-admin/`
- `private/utilities/tools/paypal-csm/`

Observed FND sandbox datum roots:

- `data/sandbox/agro-erp/sources/`
- `data/sandbox/fnd-ebi/sources/`
- `data/sandbox/maps/sources/`

Observed TFF state during this audit:

- no tenant-local `private/utilities/tools/*` files were found
- no sandbox tool source trees were found under `data/sandbox/`

These paths are still useful evidence, but they are not proof that V2 currently
surfaces or enables those tools.

## Legacy inventory

Legacy repo evidence still exists in two main layers.

Legacy V1 tool packages:

- `packages/tools/aws_csm`
- `packages/tools/paypal_csm`
- `packages/tools/analytics`
- `packages/tools/operations`
- `packages/tools/keycloak_sso`
- `packages/tools/newsletter_admin`

Legacy V1 portal tool surfaces:

- `aws_platform_admin`
- `aws_tenant_actions`
- `maps`-adjacent tooling through datum and mediation docs
- `agro_erp`
- `fnd_ebi`
- `data_tool`
- `fnd_provisioning`
- `operations`
- `tenant_progeny_profiles`
- `paypal_service_agreement`
- `paypal_tenant_actions`
- `paypal_demo`
- `newsletter_admin`
- `legacy_admin`

## Documentation classification

| Document or family | Classification | Why |
| --- | --- | --- |
| `docs/contracts/tool_state_and_datum_authority.md` | current V2 truth | Correctly preserves shell-owned attachment and config-vs-datum separation. |
| `docs/plans/post_mvp_rollout/runtime_entrypoints.md` | current V2 truth | Already tracks the current shared runtime contract, including trusted-tenant entrypoints. |
| `docs/plans/post_mvp_rollout/post_aws_tool_platform/tool_descriptor_contract.md` | current V2 truth | Correctly fixes catalog-driven shell-owned descriptors. |
| `docs/records/T-007-investigation.md` | partial carry-forward evidence | Strong AWS-CSM sandbox analysis; still investigation-only. |
| `docs/records/T-010-implementation.md` | partial carry-forward evidence | Strong AWS-CSM onboarding reference and proof of Band 4 implementation. |
| `docs/plans/post_mvp_rollout/post_aws_tool_platform/runtime_entrypoint_catalog.md` | stale doc drift | It listed only three admin entrypoints before this audit pass. |
| `docs/wiki/legacy/runtime-build/portal-config-model.md` | legacy-only | Accurate V1 config authority, but not the current V2 tool model. |
| `docs/wiki/legacy/tools/tool-layer-mediation.md` | legacy-only | Useful mediation evidence, but its config-driven launch model is not current V2 truth. |
| `docs/plans/legacy/v1-tool_dev.md` | legacy-only | Strong evidence for tool state and datum authority, but not a V2 structural template. |

## Findings

1. Current V2 already has a real admin tool registry, runtime catalog, and live
   deployed tool-bearing admin shell.
2. The live state file `private/config.json` still carries V1-shaped
   `tools_configuration`, but current V2 does not consume it for visibility or
   launch.
3. A forward-compatible V2 tool gate can be added to `private/config.json`, but
   it must be a new section and must not revive `tools_configuration` as the
   canonical source of truth.
4. AWS and AWS-CSM are the only positive V2 reference family for future tools.
5. Maps and AGRO-ERP have the strongest non-AWS live evidence because their
   sandbox/source roots still exist and V2 now has datum-recognition seams that
   can support future read-only inspection surfaces.
6. Several legacy tools are better treated as crosswalk or retirement topics
   rather than one-to-one V2 recreations.

## Forward decision recorded by this audit

Use the following forward model for V2.3 planning:

- shell registry stays canonical for legality, ordering, routing, and audience
- `private/config.json.tool_exposure` becomes the new instance-level visibility
  and enablement gate
- the gate is `hide-and-block`
- missing `tool_exposure` entries are hidden and unlaunchable
- legacy `tools_configuration` remains migration evidence only

## Packet created from this audit

This audit is paired with:

- [../contracts/tool_exposure_and_admin_activity_bar_contract.md](../contracts/tool_exposure_and_admin_activity_bar_contract.md)
- [../plans/v2.3-tool_exposure_and_admin_activity_bar_alignment.md](../plans/v2.3-tool_exposure_and_admin_activity_bar_alignment.md)
- [../plans/v2.3-tool_surface_packet/README.md](../plans/v2.3-tool_surface_packet/README.md)
