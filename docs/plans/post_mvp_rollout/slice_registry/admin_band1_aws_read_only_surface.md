# Slice ID

`admin_band1.aws_read_only_surface`

## Status

`implemented_trusted_tenant_read_only`

## Record-only note

This slice is already implemented. Keep this file only as slice-spec history.
Use [../../../records/11-admin_band_1_aws_read_only_surface.md](../../../records/11-admin_band_1_aws_read_only_surface.md) for completion evidence and [../current_planning_index.md](../current_planning_index.md) for current active planning.

## Purpose

Provide the first trusted-tenant-safe tool-bearing surface: a read-only AWS operational visibility slice launched through the admin shell and registry.

## Client value

This restores real admin utility quickly by showing AWS mailbox readiness, newsletter operational posture, and handoff status without introducing writes.

## Rollout band

`Admin Band 1 Trusted-Tenant AWS Read-Only`

## Exposure status

`trusted_tenant_read_only`

## Owning layers

- `packages/modules/cross_domain/aws_operational_visibility/`
- `packages/ports/aws_read_only_status/`
- `packages/adapters/filesystem/aws_read_only_status.py`
- `instances/_shared/runtime/` for one AWS read-only admin runtime entrypoint launched from the registry

## Required ports

- `packages/ports/aws_read_only_status/`

## Required adapters

- `packages/adapters/filesystem/aws_read_only_status.py`

## Required runtime composition

- one shared runtime entrypoint: `admin.aws.read_only`
- launchable only through the admin shell registry

## Required tests

- tool-surface unit loop for AWS read-only semantics
- contract loop for the approved AWS read-only seam
- adapter loop for the approved AWS read-only adapter
- integration loop for admin-shell-to-AWS-read-only launch
- architecture boundary loop proving the shell still owns discoverability and launch legality
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- `Admin Band 0` slices must already be stable
- standalone `newsletter-admin` must not be present as a launchable surface
- the slice must expose no writes and no secret-bearing values
- Gmail verification state must remain evidence-based only
- launch resolution must remain shell-owned via the registry

## Out of scope

- provisioning writes
- manual newsletter send
- PayPal
- analytics
- Maps
- AGRO-ERP
- raw credential display

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/portal/api/admin_integrations.py`
- `packages/tools/aws_csm/*`
- `docs/plans/tool_dev.md`
- `docs/plans/news_letter_workflow_correction.md`

Warnings:

- do not recreate a mixed AWS plus PayPal plus newsletter dashboard
- do not let AWS become the shell entry by convenience
- do not let compatibility-read progeny newsletter fields override the canonical newsletter operational profile

## Implementation ordering

- follows `admin_band0.shell_entry`, `admin_band0.home_status`, and `admin_band0.tool_registry`
- first real tool-bearing slice

## Frozen questions

- whether dispatch-health visibility belongs in the first read-only slice or a later AWS follow-up slice
