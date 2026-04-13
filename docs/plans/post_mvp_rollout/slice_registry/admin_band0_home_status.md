# Slice ID

`admin_band0.home_status`

## Status

`implemented_internal`

## Record-only note

This slice is already implemented. Keep this file only as slice-spec history.
Use [../../../records/10-admin_band_0_internal_admin_replacement.md](../../../records/10-admin_band_0_internal_admin_replacement.md) for completion evidence and [../current_planning_index.md](../current_planning_index.md) for current active planning.

## Purpose

Provide the default read-only admin orientation surface that shows the current admin band, exposure posture, available slices, and shared runtime health.

## Client value

This tells an operator what is intentionally available before any tool slice is exposed, and prevents AWS or any later tool from becoming the accidental landing page.

## Rollout band

`Admin Band 0 Internal Admin Replacement`

## Exposure status

`internal-only`

## Owning layers

- `packages/modules/cross_domain/local_audit/` for narrow local operational health projection where useful
- `packages/ports/audit_log/` for narrow audit-health reads if needed
- `packages/adapters/filesystem/` for the same bounded read behavior
- `instances/_shared/runtime/` for default landing-surface composition through the admin shell entry

## Required ports

- existing `audit_log` only

## Required adapters

- existing filesystem `audit_log` adapter only

## Required runtime composition

- no second public runtime entrypoint
- extend `admin.shell_entry` so the home/status surface is the default admin landing view

## Required tests

- local-audit unit loop for any health-summary projection added
- `audit_log` contract loop if bounded status reads are extended
- adapter loop for any bounded status-read behavior
- integration loop for the default admin landing payload
- architecture boundary loop for touched layers
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- clearly marks each tool slice as either launchable or still gated
- exposes no direct launch side effects
- exposes no provider-secret or instance-path data

## Out of scope

- provider-specific deep status
- tool launch controls
- writable actions
- AWS, CTS-GIS, and AGRO detail payloads beyond the registry-linked availability posture

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/app.py`
- `instances/_shared/runtime/flavors/fnd/portal/api/config.py`
- `instances/_shared/runtime/flavors/fnd/portal/services/local_audit_log.py`

Warnings:

- do not recreate a broad config dashboard
- do not let runtime own operational status semantics

## Implementation ordering

- follows `admin_band0.shell_entry`
- should land before the tool registry/launcher is exposed as an active admin surface

## Frozen questions

- whether the first home/status surface uses local-audit-backed health summary or only shell/runtime posture data
