# AWS Tenant Actions

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `carry_forward`  
V2 tool id target: `aws_csm_onboarding`  
Config gate target: `tool_exposure.aws_csm_onboarding`  
Audience: `trusted-tenant-admin`

## Current code, docs, and live presence

- Current code: no separate V2 `aws_tenant_actions` tool id exists.
- Legacy code: V1 portal surface exists as a separate tool/action family.
- Live presence: bounded mailbox action work already lives under
  `aws_csm_onboarding` in the current V2 admin shell.

## Reusable evidence vs legacy baggage

- Reusable evidence: mailbox initiation, staged verification, and bounded action
  workflows.
- Legacy baggage: mixed action bundles, legacy route names, and direct V1
  mutation flows.

## Required V2 owner layers and dependencies

- Shell and runtime: future action expansion belongs under the existing
  onboarding tool, or under a new approved slice if the action family escapes
  onboarding.
- Semantic owner: `aws_csm_onboarding` remains the first owner.
- Port and adapter: keep mailbox profile and cloud-port boundaries explicit.

## Admin activity-bar behavior

- No separate activity-bar item is approved.
- The crosswalk target is the existing `AWS-CSM Mailbox Onboarding` tool.
- Visibility is controlled through `tool_exposure.aws_csm_onboarding`.

## Carry-forward and do-not-carry-forward

- Carry forward only action flows that fit the bounded onboarding model.
- Do not recreate `aws_tenant_actions` as a second writable AWS action tool by
  convenience.
