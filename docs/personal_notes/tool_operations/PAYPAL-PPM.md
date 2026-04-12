# PAYPAL-PPM

Canonical name: `PAYPAL-PPM`  
Tool family posture: `unify all PayPal work under one V2.3 family`  
Primary exposure: `internal-admin` first  
Primary read/write posture: `read-only first, bounded-write later`

## 1. Completion intent

`PAYPAL-PPM` should be the single PayPal family for the portal.

It should absorb all PayPal-related work into one root tool, including:

- agreement posture
- operational PayPal state
- billing and payment-management posture
- webhook-driven activity visibility
- later bounded tenant/payment actions if justified

It should not remain split across separate service-agreement, tenant-actions, or demo roots.

## 2. Source basis

Repo sources investigated:

- `docs/plans/v2.3-tool_surface_packet/paypal_service_agreement.md`
- `docs/plans/v2.3-tool_surface_packet/paypal_tenant_actions.md`
- `docs/plans/v2.3-tool_surface_packet/paypal_demo.md`
- `docs/contracts/legacy/paypal_csm.md`
- `docs/wiki/legacy/tools/member-service-integrations.md`

These show that current packet thinking already wants PayPal treated as a later family, with service agreement as the family lead, tenant actions as a child, and demo flows retired.

## 3. Core V2.3 position

The right family shape is one PayPal root tool with multiple sub-slices.

That family should be organized around operator value, not historical route names.

The family should be:

- service-agreement led
- webhook-observed
- profile-backed
- read-only first
- bounded-write only where policy is explicit

## 4. Stable source-of-truth model

The stable authority layers should be:

- PayPal operational state documents under the PayPal tool family root
- agreement and billing relationship state
- webhook-derived activity/event records
- non-secret routing and integration refs
- derived summaries and alerts

Webhook activity should be a first-class observation surface, not a side effect hidden behind admin actions.

## 5. Similarity to FND-EBI

The correct similarity to `FND-EBI` is structural:

- both should gather operator meaning from stable files and projections
- both should be read-oriented first
- both should reconstruct useful visibility from bounded source families

The difference is that `PAYPAL-PPM` is provider-event and agreement oriented, while `FND-EBI` is site/service analytics and operational visibility oriented.

## 6. Family structure

### 6.1 Agreement posture
The first required slice.

Must summarize:

- service agreement state
- account-on-file posture
- billing relationship readiness
- operational provider status

### 6.2 Webhook activity
The second required slice.

Must summarize:

- recent webhook events
- activity types
- failures or replay needs
- provider-facing event health
- bounded operational traces

### 6.3 Payment-management actions
Later bounded-write work only.

### 6.4 Tenant/payment actions
Later child slices, not a separate family root.

## 7. Completion slices

### Slice 1 — read-only agreement and provider posture
This is the first completion slice.

### Slice 2 — webhook activity visibility
This is the second completion slice.

### Slice 3 — bounded operator payment actions
Later.

### Slice 4 — bounded tenant/payment actions
Later.

## 8. Do not carry forward

Do not carry forward:

- a separate `paypal_service_agreement` root tool
- a separate `paypal_tenant_actions` root tool
- any `paypal_demo` root tool
- mixed checkout/demo/provider-admin bundles
- demo-first family design
- legacy route-family naming as the architecture

## 9. Acceptance boundary

`PAYPAL-PPM` is complete when all PayPal-related operator work can be described as slices of one family rooted in agreement posture and webhook-observed activity, with later bounded writes added only when policy is explicit.

## 10. Recommended V2.3 landing statement

Use `PAYPAL-PPM` as one PayPal family. Make agreement posture and webhook activity the first two slices. Treat all other PayPal actions as later bounded sub-slices rather than separate tools.
