# AWS

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Family root: [AWS-CSM](aws_csm.md)\
Packet role: `implemented slice doc`

Disposition: `current_v2`  
V2 tool id: `aws`  
Config gate target: `tool_exposure.aws`  
Audience: `trusted-tenant-admin`

## Current code, docs, and live presence

- Current code: `admin_band1.aws_read_only_surface`,
  `admin.aws.read_only`, and the shell-owned registry entry already exist.
- Live presence: FND and TFF both currently expose `aws` through
  `POST /portal/api/v2/admin/shell`.
- Current docs: post-AWS platform docs, AWS runtime records, and the shared
  runtime catalog all treat this as the reference read-only tool.

## Reusable evidence vs legacy baggage

- Reusable evidence: AWS operational visibility, live profile mapping,
  read-only runtime composition, and IAM/SES reference material.
- Legacy baggage: mixed provider dashboards, config-driven launch, and V1 route
  shapes must not return.

## Required V2 owner layers and dependencies

- Shell registry: existing `AdminToolRegistryEntry` for `aws`.
- Runtime entrypoint: existing `admin.aws.read_only`.
- Semantic owner: `packages/modules/cross_domain/aws_operational_visibility/`.
- Port and adapter: `packages/ports/aws_read_only_status/` and
  `packages/adapters/filesystem/live_aws_profile.py`.
- Live state dependency: canonical live AWS status/profile file only.

## Admin activity-bar behavior

- Hidden and blocked unless `tool_exposure.aws.enabled=true`.
- Ordering, label, route, and audience remain shell-owned.
- No trusted-tenant portal activity-bar exposure is planned in this packet.

## Carry-forward and do-not-carry-forward

- Keep this as the primary read-only AWS admin surface.
- Keep it as a slice of `AWS-CSM`, not as a competing family root.
- Do not create a second `aws_read_only` tool id or a config-owned alias.
- Do not pull legacy newsletter-admin or broad provider-admin controls into this
  surface.
