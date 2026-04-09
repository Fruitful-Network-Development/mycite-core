# Slice ID

`admin_band0.shell_entry`

## Status

`candidate`

## Purpose

Create the one stable admin shell landing path that replaces the old portal's mixed provider and service navigation as the operator starting point.

## Client value

This gives operators and, later, trusted tenant admins one predictable way to enter the portal without needing provider-specific routes or legacy tabs.

## Rollout band

`Admin Band 0 Internal Admin Replacement`

## Exposure status

`internal-only`

## Owning layers

- `packages/state_machine/` for shell legality and slice selection state
- `instances/_shared/runtime/` for one admin shell runtime entrypoint

## Required ports

- none

## Required adapters

- none

## Required runtime composition

- one shared runtime entrypoint: `admin.shell_entry`

## Required tests

- state-machine loop for any new shell-entry contract additions
- integration loop for the landing payload and denied-slice behavior
- architecture boundary loop for state-machine and runtime composition
- slice gate checklist from [../../../testing/slice_gate_template.md](../../../testing/slice_gate_template.md)

## Client exposure gates

- remains internal-only until the admin runtime envelope, home/status surface, and tool registry/launcher are stable
- exposes no provider-specific semantics
- exposes no instance paths or secret-bearing fields

## Out of scope

- provider dashboards
- AWS details
- tool execution
- writable actions
- flavor-specific runtime paths

## V1 evidence and drift warnings

- `instances/_shared/runtime/flavors/fnd/app.py`
- `instances/_shared/runtime/flavors/fnd/portal/core_services/runtime.py`

Warnings:

- do not recreate host-owned service navigation
- do not let the shell entry become a semantic owner for provider slices

## Implementation ordering

- first admin-first slice
- admin home/status and tool registry may extend this entrypoint later, but they may not create parallel shell landings by convenience

## Frozen questions

- whether the admin home/status payload is fully embedded in `admin.shell_entry` or structured as its default surface view
