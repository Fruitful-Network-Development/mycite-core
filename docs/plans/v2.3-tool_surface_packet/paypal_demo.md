# PayPal Demo

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Disposition: `legacy_isolation`  
V2 tool id target: `paypal_demo`  
Config gate target: `tool_exposure.paypal_demo`  
Audience: none approved

## Current code, docs, and live presence

- Current code: no V2 `paypal_demo` tool exists.
- Legacy evidence: V1 demo-oriented portal surface exists.
- Live presence: no live V2 presence was found during this audit.

## Reusable evidence vs legacy baggage

- Reusable evidence: none that requires a dedicated V2 demo tool.
- Legacy baggage: demonstration-only flows mixed into operator tooling.

## Required V2 owner layers and dependencies

- No standalone V2 `paypal_demo` tool is approved.
- If demo material is ever needed again, it should live in tests, fixtures, or
  isolated documentation rather than an operator-facing tool.

## Admin activity-bar behavior

- Remains absent from the activity bar.
- Any reserved `tool_exposure.paypal_demo` key should stay disabled and unused.

## Carry-forward and do-not-carry-forward

- Keep `paypal_demo` as legacy evidence only.
- Do not recreate it as a V2 tool.
