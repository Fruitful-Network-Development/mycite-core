# PAYPAL-PPM

Authority: [../v2-authority_stack.md](../v2-authority_stack.md)

Canonical name: `PAYPAL-PPM`\
Packet role: `family_root`\
Queue posture: `typed family plan only`\
Primary future gate target: `tool_exposure.paypal_ppm`

## Completion intent

`PAYPAL-PPM` is the single PayPal family for V2.3.

It should absorb PayPal-related operator work into one family rooted in:

- agreement posture
- operational PayPal state
- billing and payment-management posture
- webhook-observed activity

It should not remain split across separate PayPal service-agreement,
tenant-actions, or demo roots.

## Current family truth

- No live V2 PayPal tool exists yet.
- Existing typed PayPal packet docs are retained as subordinate docs and
  crosswalk evidence, not as separate root families.

Subordinate docs under this family:

- [paypal_service_agreement.md](paypal_service_agreement.md)
- [paypal_tenant_actions.md](paypal_tenant_actions.md)
- [paypal_demo.md](paypal_demo.md)

## Core V2.3 position

The correct family shape is one PayPal root family with multiple future slices.

The family should be:

- agreement-led
- webhook-observed
- profile-backed
- read-only first
- bounded-write later where policy is explicit

## First completion sequence

### Slice 1 — agreement and provider posture

Read-only.

Must summarize:

- service agreement state
- account-on-file posture
- billing relationship readiness
- provider operational status

### Slice 2 — webhook activity visibility

Read-only.

Must summarize:

- recent webhook events
- activity types
- replay/failure posture
- provider event health

### Slice 3 — bounded operator payment actions

Later.

### Slice 4 — bounded tenant/payment actions

Later and as child slices, not a second family root.

## Do not carry forward

Do not carry forward:

- a separate `paypal_service_agreement` root tool
- a separate `paypal_tenant_actions` root tool
- any `paypal_demo` root tool
- mixed checkout/demo/provider-admin bundles
