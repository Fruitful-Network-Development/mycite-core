# PayPal Service Agreement

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Family root: [PAYPAL-PPM](paypal_ppm.md)\
Packet role: `subordinate slice direction`

Disposition: `defer`  
V2 tool id target: `paypal_service_agreement`  
Config gate target: `tool_exposure.paypal_service_agreement`  
Audience: later decision

## Current code, docs, and live presence

- Current code: no V2 PayPal tool exists.
- Legacy evidence: V1 PayPal portal surfaces and PayPal package state still
  exist.
- Live presence: FND still has `private/utilities/tools/paypal-csm/`; no live
  V2 admin-shell PayPal entry exists.

## Reusable evidence vs legacy baggage

- Reusable evidence: service-agreement workflow and PayPal operator state.
- Legacy baggage: mixed checkout/provider-admin coupling and legacy route trees.

## Required V2 owner layers and dependencies

- Any V2 version needs one explicit PayPal semantic owner and a new narrow
  contract for agreement state.
- Ports and adapters must be scoped to PayPal operational state, not copied from
  the legacy tool package wholesale.
- No runtime entrypoint is approved in the current sequence.

## Admin activity-bar behavior

- Hidden and blocked by default.
- No activity-bar item until PayPal is explicitly reopened after AWS, Maps, and
  AGRO follow-on work.

## Carry-forward and do-not-carry-forward

- Defer PayPal service-agreement work as a future slice under `PAYPAL-PPM`,
  not as a separate family root.
- Do not merge it into AWS or recreate the V1 PayPal route surface.
