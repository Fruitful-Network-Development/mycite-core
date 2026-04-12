# AWS-CSM Onboarding

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `current_v2`  
V2 tool id: `aws_csm_onboarding`  
Config gate target: `tool_exposure.aws_csm_onboarding`  
Audience: `trusted-tenant-admin`

## Current code, docs, and live presence

- Current code: `admin_band4.aws_csm_onboarding_surface`,
  `admin.aws.csm_onboarding`, and the shell-owned registry entry already exist.
- Live presence: FND and TFF both report `aws_csm_onboarding` through the live
  admin shell.
- Current docs: `T-010-implementation.md` is the strongest mailbox-onboarding
  reference for V2.

## Reusable evidence vs legacy baggage

- Reusable evidence: bounded workflow actions, confirmation policy, cloud-port
  handoff seam, and read-after-write/audit behavior.
- Legacy baggage: V1 provision routes, provider-owned launch logic, and mailbox
  workflow sprawl outside the bounded runtime contract.

## Required V2 owner layers and dependencies

- Shell registry: existing `AdminToolRegistryEntry` for `aws_csm_onboarding`.
- Runtime entrypoint: existing `admin.aws.csm_onboarding`.
- Semantic owner: `packages/modules/cross_domain/aws_csm_onboarding/`.
- Port and adapter: onboarding profile store, onboarding cloud port, and live
  AWS profile storage.
- Live state dependency: canonical mailbox profile JSON plus local-audit
  storage.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.aws_csm_onboarding.enabled=true`.
- Remains an admin-shell tool, not a trusted-tenant portal slice.
- Any future tenant-facing onboarding follow-on needs its own slice approval.

## Carry-forward and do-not-carry-forward

- Keep this as the mailbox-onboarding write tool.
- Do not backslide into V1 `/provision` route shapes or config-driven actions.
- Do not merge unrelated AWS read-only status fields into onboarding by
  convenience.
