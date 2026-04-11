# Slice ID

`admin_band2.aws_narrow_write_surface`

## Status

`implemented_trusted_tenant_narrow_write`

## Record-only note

This slice is already implemented. Keep this file only as slice-spec history.
Use [../../../records/12-admin_band_2_aws_narrow_write_surface.md](../../../records/12-admin_band_2_aws_narrow_write_surface.md) for completion evidence and [../current_planning_index.md](../current_planning_index.md) for current active planning.

## Purpose

Provide one bounded AWS operational write workflow after the AWS read-only surface is stable.

## Client value

This offers the smallest useful AWS write path without reopening the old portal's broad provider-admin surface.

## Rollout band

`Admin Band 2 Trusted-Tenant AWS Narrow Write`

## Exposure status

`trusted_tenant_narrow_write`

## Owning layers

- `packages/modules/cross_domain/aws_narrow_write/`
- `packages/ports/aws_narrow_write/`
- `packages/adapters/filesystem/aws_narrow_write.py`
- `packages/modules/cross_domain/local_audit/` for accepted write-path audit emission
- existing `packages/ports/audit_log/` plus its adapter for audit persistence
- `instances/_shared/runtime/` for one bounded AWS write runtime entrypoint

## Required ports

- `packages/ports/aws_narrow_write/`
- existing `audit_log`

## Required adapters

- `packages/adapters/filesystem/aws_narrow_write.py`
- existing filesystem `audit_log` adapter

## Required runtime composition

- one shared runtime entrypoint: `admin.aws.narrow_write`
- must remain launchable only through the admin shell registry
- must provide read-after-write confirmation

## Required tests

- AWS write-surface unit loop for bounded field validation
- contract loop for the approved AWS narrow-write seam
- adapter loop for the approved AWS narrow-write adapter
- local-audit loop for accepted write-path audit emission
- integration loop for read-after-write through the admin shell
- architecture boundary loop for shell, AWS tool slice, audit, adapter, and runtime
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- `admin_band1.aws_read_only_surface` must already be stable
- the writable field set must remain explicitly bounded
- the bounded writable field set is `selected_verified_sender` only
- manual newsletter send stays retired
- Gmail verification status may not be toggled without confirmation evidence
- rollback or manual repair instructions must exist before exposure and are recorded in [../admin_first/aws_narrow_write_recovery.md](../admin_first/aws_narrow_write_recovery.md)

## Out of scope

- manual newsletter dispatch
- broad mailbox provisioning
- raw secret editing
- PayPal or analytics writes
- Maps
- AGRO-ERP

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py`
- `instances/_shared/runtime/flavors/fnd/portal/api/newsletter_admin.py`
- `docs/plans/tool_dev.md`
- `docs/plans/news_letter_workflow_correction.md`

Warnings:

- do not revive manual admin newsletter send
- do not let runtime or adapters define AWS operational semantics
- do not grow the first write path into a broad provider-admin control plane

## Implementation ordering

- follows `admin_band1.aws_read_only_surface`
- must complete before any Maps slice is approved for build

## Frozen questions

- whether any second AWS narrow-write field family is ever approved after `selected_verified_sender`
