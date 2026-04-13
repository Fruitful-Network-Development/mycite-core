# AWS Narrow Write

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Family root: [AWS-CSM](aws_csm.md)\
Packet role: `implemented slice doc`

Disposition: `current_v2`  
V2 tool id: `aws_narrow_write`  
Config gate target: `tool_exposure.aws_narrow_write`  
Audience: `trusted-tenant-admin`

## Current code, docs, and live presence

- Current code: `admin_band2.aws_narrow_write_surface`,
  `admin.aws.narrow_write`, and the shell-owned registry entry already exist.
- Live presence: FND and TFF both currently expose `aws_narrow_write` through
  the live admin shell.
- Current docs: bounded-write patterns and runtime records already treat this as
  the reference bounded-write tool.

## Reusable evidence vs legacy baggage

- Reusable evidence: explicit writable field set, read-after-write confirmation,
  accepted-write audit emission, and recovery documentation.
- Legacy baggage: broad AWS mutation surfaces, direct provider routes, and
  ad-hoc mailbox actions outside the bounded contract.

## Required V2 owner layers and dependencies

- Shell registry: existing `AdminToolRegistryEntry` for `aws_narrow_write`.
- Runtime entrypoint: existing `admin.aws.narrow_write`.
- Semantic owner: `packages/modules/cross_domain/aws_narrow_write/`.
- Port and adapter: `packages/ports/aws_narrow_write/` and the live-profile
  filesystem adapter.
- Live state dependency: canonical live AWS profile plus local-audit storage.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.aws_narrow_write.enabled=true`.
- Remains a separate activity-bar item because write posture differs from the
  read-only AWS surface.
- No tenant-portal exposure is planned here.

## Carry-forward and do-not-carry-forward

- Keep this as the only bounded-write AWS tool unless a later slice explicitly
  approves another one.
- Keep it as a slice of `AWS-CSM`, not as a separate family root.
- Do not let config widen the field set or bypass audit/read-after-write.
- Do not merge onboarding workflow semantics into this tool id by convenience.
