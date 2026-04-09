# Frozen Decisions For The Current Band

Authority: [../authority_stack.md](../authority_stack.md)

This file records what is deliberately frozen so future agents do not widen scope by convenience.

## Current band

- Current exposure band remains `Band 0 Internal Only`.
- Current build target is `Band 1 Trusted-Tenant Read-Only`.

## Frozen decisions

- The next client-visible band is read-only only.
- No Band 2 writable workflow may be implemented until at least one Band 1 slice passes its exposure gate.
- The preferred next build order is:
  1. `band1.portal_home_tenant_status`
  2. one of `band1.audit_activity_visibility` or `band1.operational_status_surface`
  3. Band 2 writable work only after a Band 1 slice is safely exposed
- No tool or sandbox work is part of the current band.
- No flavor-specific runtime expansion is part of the current band.
- No second public runtime entrypoint may be added without a slice registry entry and runtime catalog update.
- `external_events` remains out of the first rollout band.
- Hosted and progeny breadth remains frozen. A later slice may use hosted or progeny evidence, but it may not widen that area without an explicit decision.
- Provider-admin flows such as newsletter, AWS-CMS, and PayPal do not define the shared client rollout path.
- `local_audit` remains a narrow semantic owner. It must not grow into a generic event framework.
- `packages/state_machine/mediation_surface` remains deferred.

## Writable-candidate freeze

- The first writable candidate is a bounded publication-backed profile basics slice only.
- That candidate may be specified now, but it is not approved for implementation in the current band.
- No alternate writable candidate may displace it without an explicit decision record.

## Questions explicitly frozen

- Whether tenant summaries eventually draw from publication only or from a publication plus alias or progeny composite.
- Whether operational status and audit visibility stay separate slices or later merge into one read-only shell surface.
- Whether broader analytics becomes a Band 2 or Band 3 concern.
