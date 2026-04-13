# AWS Platform Admin

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Family root: [AWS-CSM](aws_csm.md)\
Packet role: `legacy crosswalk`

Disposition: `carry_forward`  
V2 tool id target: `aws`  
Config gate target: `tool_exposure.aws`  
Audience: `trusted-tenant-admin`

## Current code, docs, and live presence

- Current code: no separate V2 `aws_platform_admin` tool id exists.
- Legacy code: V1 portal tool surface exists under the old FND portal runtime.
- Live presence: the live V2 admin shell already exposes `aws`; that is the
  modern replacement surface for most platform-admin visibility.

## Reusable evidence vs legacy baggage

- Reusable evidence: mailbox readiness, SES/IAM visibility, and operator-facing
  AWS status cards.
- Legacy baggage: mixed provider dashboards, legacy route families, and
  config-driven mounting.

## Required V2 owner layers and dependencies

- Shell and runtime: extend the existing `aws` tool only when new read-only
  fields are needed.
- Semantic owner: keep additions inside AWS operational visibility.
- Port and adapter: keep using the existing read-only AWS seam.
- No new V2 tool id or separate runtime entrypoint is approved here.

## Admin activity-bar behavior

- No separate activity-bar item.
- The legacy surface crosswalks into the existing `AWS Admin` tool.
- Visibility is controlled only through `tool_exposure.aws`.

## Carry-forward and do-not-carry-forward

- Carry forward only the read-only operator visibility that fits the current AWS
  tool.
- Do not recreate `aws_platform_admin` as a standalone V2 tool, route, or icon.
