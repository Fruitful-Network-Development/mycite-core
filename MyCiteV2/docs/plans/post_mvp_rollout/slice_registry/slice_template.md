# Slice Template

Authority: [../../authority_stack.md](../../authority_stack.md)

Use this template before any post-MVP slice is implemented.

## Slice ID

Use one of:

- `band<number>.<short_name>`
- `admin_band<number>.<short_name>`

## Status

Choose one:

- `candidate`
- `approved_for_build`
- `implemented_internal`
- `client_visible`
- `frozen`
- `superseded`

## Purpose

State the smallest user-facing surface or workflow this slice creates.
Use one or two sentences.

## Client value

State why a client, tenant, or operator should care about this slice now.

## Rollout band

Name exactly one band from:

- [../portal_rollout_bands.md](../portal_rollout_bands.md), or
- [../admin_first/admin_first_rollout_band.md](../admin_first/admin_first_rollout_band.md)

## Exposure status

State whether the slice is:

- internal-only
- planned_not_approved_for_build
- approved_for_build
- implemented_internal
- approved_for_exposure
- client_visible

## Owning layers

List only the layers that must change.
Name where semantics live, where contracts live, where adapter behavior lives, and where runtime composition lives.

## Required ports

List only the ports that must exist or change for this slice.
If no new port work is needed, say so explicitly.

## Required adapters

List only the adapters that must exist or change for this slice.
Do not broaden to speculative future adapters.

## Required runtime composition

Name the one runtime entrypoint this slice requires.
If an existing entrypoint is extended, explain why that does not create a second runtime path.

## Required tests

List the exact loops that must pass:

- unit
- contract
- adapter
- integration
- architecture boundary
- slice gate record

## Client exposure gates

List the gate conditions from [../client_exposure_gates.md](../client_exposure_gates.md) that matter most for this slice.
Add any slice-specific client-safety constraint here.

## Out of scope

List the tempting adjacent work that must stay out of this slice.
Be explicit about non-goals.

## V1 evidence and drift warnings

Link the v1 workflow evidence that informed this slice.
Then name the drift patterns that must not return.

## Implementation ordering

State where this slice sits relative to the other current candidates.
If another slice or seam must exist first, say so explicitly.

## Frozen questions

List the questions that remain intentionally unresolved for this slice.
Do not silently solve them in implementation.
