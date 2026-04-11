# Slice ID

`band1.portal_home_tenant_status`

## Status

`candidate`

## Purpose

Provide one read-only landing surface that tells a trusted tenant where they are, which tenant profile is in view, which rollout band the portal is currently in, and which slices are intentionally available.

## Client value

This slice gives a safe first client-visible orientation surface. It reduces confusion and prevents users from mistaking hidden internal surfaces for supported workflows.

## Rollout band

`Band 1 Trusted-Tenant Read-Only`

## Exposure status

`planned_not_approved_for_build`

## Owning layers

- `packages/state_machine/` for shell context and navigation legality
- `packages/modules/domains/publication/` for read-only tenant summary semantics
- `packages/ports/datum_store/` for publication data access
- `packages/adapters/filesystem/` for the first datum-store adapter
- `instances/_shared/runtime/` for one read-only composition entrypoint

## Required ports

- `datum_store` read-only lookup for one publication-backed tenant summary projection

## Required adapters

- filesystem-backed `datum_store` only

## Required runtime composition

- one shared-runtime read-only entrypoint
- no flavor-specific runtime path
- no tool or sandbox composition

## Required tests

- publication unit loop for the tenant summary projection
- `datum_store` contract loop
- filesystem `datum_store` adapter loop
- integration loop for the read-only home path
- architecture boundary loop for touched layers
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- must expose no hidden write actions
- must expose no internal instance identifiers or filesystem paths
- must show rollout band and exposure status explicitly
- must stay read-only even when later writable slices exist

## Out of scope

- editing
- analytics
- contracts
- reference workflows
- tools
- sandboxes
- admin integrations
- media editing

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/app.py`
- `instances/_shared/runtime/flavors/fnd/portal/core_services/runtime.py`
- `instances/_shared/runtime/flavors/fnd/portal/api/aliases.py`

Warnings:

- do not recreate v1 host-owned service navigation
- do not couple alias or progeny workspace logic into the runtime layer

## Implementation ordering

- first deferred Band 1 slice after the hardening sequence, retirement ledger,
  and Phase 11 retirement review are closed
- must be reopened before any other deferred Band 1 or Band 2 slice advances

## Frozen questions

- whether the first tenant summary is publication-only or a later composite with alias or progeny read models
