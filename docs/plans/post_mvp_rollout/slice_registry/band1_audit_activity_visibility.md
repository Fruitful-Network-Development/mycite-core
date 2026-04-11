# Slice ID

`band1.audit_activity_visibility`

## Status

`candidate`

## Purpose

Expose one read-only recent local-audit surface so a trusted tenant can see what the portal accepted and persisted.

## Client value

This slice provides trustworthy visibility into accepted actions without exposing externally meaningful event handling, tools, or sandbox state.

## Rollout band

`Band 1 Trusted-Tenant Read-Only`

## Exposure status

`planned_not_approved_for_build`

## Owning layers

- `packages/modules/cross_domain/local_audit/` for read-only audit record projection
- `packages/ports/audit_log/` for bounded audit-log read contracts
- `packages/adapters/filesystem/` for audit-log persistence and bounded read behavior
- `instances/_shared/runtime/` for one read-only composition entrypoint

## Required ports

- extend `audit_log` with a bounded recent-window read contract for local-audit visibility

## Required adapters

- extend the filesystem `audit_log` adapter to satisfy the bounded recent-window read contract

## Required runtime composition

- one shared-runtime read-only entrypoint for recent audit visibility
- no flavor-specific runtime path

## Required tests

- local-audit unit loop for read-only activity projection
- `audit_log` contract loop for bounded recent-window reads
- filesystem adapter loop for bounded read behavior
- integration loop for end-to-end visibility
- architecture boundary loop for `local_audit`, `audit_log`, filesystem adapter, and runtime
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- local audit only in Band 1
- no `external_events` merge
- no search, export, or arbitrary query surface
- fixed recent-window behavior only

## Out of scope

- `external_events`
- inbox visibility
- annotations
- export
- free-text search
- custom filtering

## V1 evidence and drift warnings

- `mycite_core/local_audit/store.py`
- `instances/_shared/runtime/flavors/fnd/portal/services/local_audit_log.py`
- `instances/_shared/runtime/flavors/fnd/portal/core_services/runtime.py`
- `mycite_core/external_events/feed.py`

Warnings:

- do not merge local audit and externally meaningful events in the first read-only band
- do not hide activity semantics inside runtime composition

## Implementation ordering

- third deferred slice after `band1.portal_home_tenant_status` and
  `band1.operational_status_surface`
- may share runtime composition helpers with earlier deferred Band 1 slices
  only if runtime remains composition-only

## Frozen questions

- whether Band 1 activity visibility stays local-audit only or later gains an explicitly separate `external_events` companion surface
