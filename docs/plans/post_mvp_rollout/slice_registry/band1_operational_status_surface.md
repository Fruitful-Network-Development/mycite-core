# Slice ID

`band1.operational_status_surface`

## Status

`candidate`

## Purpose

Expose one read-only operational status surface that shows the current rollout band, exposure status, audit persistence health, and whether the portal is intentionally operating in a read-only or writable posture.

## Client value

This slice gives trusted tenants a stable answer to “is this portal safe to use right now, and what is intentionally available?”

## Rollout band

`Band 1 Trusted-Tenant Read-Only`

## Exposure status

`planned_not_approved_for_build`

## Owning layers

- `packages/modules/cross_domain/local_audit/` for recent persistence and health summary projection
- `packages/ports/audit_log/` for bounded recent-window or health-summary reads
- `packages/adapters/filesystem/` for the same bounded read behavior
- `instances/_shared/runtime/` for one read-only composition entrypoint

## Required ports

- either the same bounded recent-window read contract used by audit visibility or one narrower explicit health-summary contract on `audit_log`

## Required adapters

- filesystem `audit_log` adapter extended only as needed for the chosen bounded status read

## Required runtime composition

- one shared-runtime read-only entrypoint
- no flavor-specific branching

## Required tests

- local-audit unit loop for operational status summary derivation
- `audit_log` contract loop for the selected bounded status read
- filesystem adapter loop for status-read conformance
- integration loop for operational status runtime composition
- architecture boundary loop for touched layers
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- no provider-specific admin controls
- no AWS, newsletter, or PayPal details in Band 1
- no hidden write action behind status toggles
- rollout band and exposure posture must be explicit in the response

## Out of scope

- analytics dashboards
- admin integrations
- newsletter readiness
- PayPal readiness
- alerting frameworks
- tools
- sandboxes

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py`
- `instances/_shared/runtime/flavors/fnd/portal/api/website_analytics.py`
- `instances/_shared/runtime/flavors/fnd/app.py`

Warnings:

- do not rebuild provider-admin dashboards as the first operational slice
- do not let runtime become the owner of status semantics

## Implementation ordering

- candidate for Band 1 after the portal home slice is specified
- may be implemented before broader analytics work

## Frozen questions

- whether operational status remains a standalone slice or later becomes a bounded card on the home surface
