# Admin Shell Entry Requirements

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This file defines the single stable admin shell entry required before tool-bearing admin rollout.

## Functional claim

The admin shell entry is the one stable landing path for internal operators and, later, trusted tenant admins.

It is not a provider dashboard.
It is not a tool implementation.
It is not a second semantic owner.

## Required properties

- One public runtime entrypoint only for the admin shell landing path.
- Composition-only behavior under `instances/_shared/runtime/`.
- Shell legality continues to live in `packages/state_machine/`.
- The shell entry exposes:
  - current admin band
  - exposure posture
  - current tenant scope
  - active admin surface id
  - available admin slices as provided by the registry/launcher
- The shell entry returns explicit errors when an unapproved slice is requested.

## Ownership

| Concern | Owner | Forbidden owner |
|---|---|---|
| shell verbs, focus, and navigation legality | `packages/state_machine/` | tools, runtime wrappers, provider adapters |
| slice discoverability | shell-owned registry/launcher surface | tool packages |
| runtime composition | `instances/_shared/runtime/` | tools and modules |
| provider semantics | future tool slices or modules that own them | shell entry |

## In scope for the shell entry

- one stable landing entrypoint
- one default admin home/status payload
- one path into the tool registry/launcher
- stable posture reporting

## Out of scope for the shell entry

- provider-specific semantics
- tool launch side effects
- writable actions
- direct provider routing
- sandbox or workbench orchestration

## Tests required before the shell entry is considered stable

- state-machine loop for any new shell-facing contract additions
- runtime boundary loop proving composition-only behavior
- integration loop for landing payload shape and denied-slice behavior
- architecture boundary loop proving no tool or provider imports define shell truth

## Replacement rule

The old portal is not considered operationally replaced until this shell entry is the only stable starting point for admin work.
