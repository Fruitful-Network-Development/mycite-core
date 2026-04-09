# Slice ID

`admin_band0.tool_registry`

## Status

`candidate`

## Purpose

Provide one shell-owned registry and launcher surface that lists approved admin slices and launches them through cataloged runtime entrypoints only.

## Client value

This gives operators a stable way to discover future admin tools without letting tool code define discoverability, routing, or shell legality.

## Rollout band

`Admin Band 0 Internal Admin Replacement`

## Exposure status

`internal-only`

## Owning layers

- `packages/state_machine/` for any shell selection state needed to choose an approved tool slice
- `instances/_shared/runtime/` for registry composition and launch resolution through the admin shell entry

## Required ports

- none

## Required adapters

- none

## Required runtime composition

- no second public runtime entrypoint
- extend `admin.shell_entry` with one registry payload and launch-resolution path

## Required tests

- registry payload-shape test
- deny-by-default test for unapproved entries
- integration loop for launch resolution through `admin.shell_entry`
- architecture boundary loop proving no tool packages define registry truth
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- `newsletter-admin` must not appear as a standalone entry
- AWS may be listed as planned, but not launchable for trusted-tenant use until its own slice gate passes
- Maps and AGRO-ERP must remain blocked behind AWS-first ordering

## Out of scope

- direct tool execution
- dynamic package scanning
- provider-specific fallback routes
- launch side effects beyond approved entrypoint resolution

## V1 evidence and drift warnings

- `instances/_shared/portal/application/service_tools.py`
- `instances/_shared/portal/application/shell/tools.py`
- `instances/_shared/runtime/flavors/fnd/portal/tools/runtime.py`

Warnings:

- do not let tools define shell legality
- do not rebuild legacy tool tabs and service navigation as the source of truth

## Implementation ordering

- follows `admin_band0.shell_entry`
- may land alongside or immediately after `admin_band0.home_status`
- must be stable before `admin_band1.aws_read_only_surface` is implemented

## Frozen questions

- whether the first registry payload is embedded directly into the home/status surface or rendered as a separate admin shell view
