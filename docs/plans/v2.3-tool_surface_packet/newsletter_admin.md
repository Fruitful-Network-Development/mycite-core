# Newsletter Admin

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Family root: [AWS-CSM](aws_csm.md)\
Packet role: `retired crosswalk`

Disposition: `discard`  
V2 tool id target: `newsletter_admin`  
Config gate target: `tool_exposure.newsletter_admin`  
Audience: none approved

## Current code, docs, and live presence

- Current code: no V2 `newsletter_admin` tool exists.
- Legacy evidence: V1 standalone tool and live FND utility files still exist.
- Current V2 posture: admin-first parity docs already say standalone
  newsletter-admin should not be rebuilt as its own shared portal tool.

## Reusable evidence vs legacy baggage

- Reusable evidence: newsletter operational state belongs inside AWS mailbox
  tooling where still relevant.
- Legacy baggage: standalone newsletter-admin routes and tool identity.

## Required V2 owner layers and dependencies

- No standalone V2 tool is approved under this name.
- Any surviving mailbox/newsletter functionality should stay inside the AWS or
  AWS-CSM family under explicit slice approval.

## Admin activity-bar behavior

- Must remain absent from the activity bar.
- `tool_exposure.newsletter_admin` should remain omitted or false.

## Carry-forward and do-not-carry-forward

- Carry forward only the operational evidence that fits AWS-owned slices.
- Do not recreate `newsletter_admin` as a standalone V2 tool.
