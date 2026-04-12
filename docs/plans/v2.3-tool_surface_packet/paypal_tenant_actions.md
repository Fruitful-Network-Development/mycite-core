# PayPal Tenant Actions

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `defer`  
V2 tool id target: `paypal_tenant_actions`  
Config gate target: `tool_exposure.paypal_tenant_actions`  
Audience: later decision

## Current code, docs, and live presence

- Current code: no V2 `paypal_tenant_actions` tool exists.
- Legacy evidence: V1 portal surface exists as part of the older PayPal family.
- Live presence: no live V2 admin-shell PayPal surface exists.

## Reusable evidence vs legacy baggage

- Reusable evidence: bounded tenant action flows may still matter in a future
  PayPal tool family.
- Legacy baggage: mixed checkout, demo, and provider-admin flows bundled
  together.

## Required V2 owner layers and dependencies

- Any V2 version should sit under a single PayPal semantic owner, not a direct
  port of the old action routes.
- It likely becomes a bounded-write follow-on under a future PayPal family.
- No runtime entrypoint or shell descriptor is approved yet.

## Admin activity-bar behavior

- Hidden and blocked by default.
- No activity-bar item until a PayPal family is explicitly approved.

## Carry-forward and do-not-carry-forward

- Defer until a real PayPal follow-on sequence exists.
- Do not recreate the old tenant-actions route shape or config-driven exposure.
