# Slice ID

`band2.profile_basics_write_surface`

## Status

`candidate`

## Purpose

Allow a trusted tenant to update a tightly bounded set of publication-backed profile basics:

- display title
- short summary
- contact email
- public website URL

## Client value

This slice is the smallest coherent writable workflow that offers real client value without pulling in tools, sandboxes, or broad content management.

## Rollout band

`Band 2 Trusted-Tenant Writable Slice`

## Exposure status

`planned_not_approved_for_build`

## Owning layers

- `packages/modules/domains/publication/` for profile-basics validation and write semantics
- `packages/ports/datum_store/` for bounded publication read and write
- `packages/modules/cross_domain/local_audit/` for write-path audit emission
- `packages/adapters/filesystem/` for `datum_store` plus the existing `audit_log` adapter
- `instances/_shared/runtime/` for one write composition entrypoint

## Required ports

- `datum_store` bounded read and write contract for one publication-backed profile document or datum
- existing `audit_log` for audit emission

## Required adapters

- filesystem-backed `datum_store`
- existing filesystem-backed `audit_log`

## Required runtime composition

- one shared-runtime write entrypoint
- explicit read-after-write response path
- no flavor-specific branching

## Required tests

- publication unit loop for bounded field validation
- `datum_store` contract loop
- filesystem `datum_store` adapter loop
- local-audit unit and integration checks for write-path audit emission
- end-to-end integration loop for read-after-write
- architecture boundary loop for publication, `datum_store`, filesystem adapter, local audit, and runtime
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- Band 1 slices must already be stable
- writable field set must remain exactly bounded
- read-after-write must be proven
- accepted writes must emit local audit records
- rollback or manual repair instructions must exist before exposure

## Out of scope

- media or image editing
- section layout editing
- contracts
- reference exchange
- analytics
- newsletter settings
- tenant secrets
- hosted and progeny workspace edits
- multi-record mutation

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/portal/api/tenant_progeny.py`
- `instances/_shared/runtime/flavors/fnd/portal/api/aliases.py`
- `mycite_core/publication/profile_paths.py`

Warnings:

- do not recreate progeny workspace editing as the first writable slice
- do not let runtime or adapter code define publication semantics

## Implementation ordering

- specify during Band 1
- do not implement until at least one Band 1 slice passes its exposure gate

## Frozen questions

- whether the first writable profile basics write path should stay publication-only or later compose with alias or progeny read models
