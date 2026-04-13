# Future Tool Drop-In Contract

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

Future post-AWS tools must be implemented one slice at a time.

## Required work packet

A future tool implementation prompt should name:

- one slice file
- one semantic owner
- one port seam
- one adapter family when outward IO is needed
- one runtime entrypoint
- one shell-owned registry descriptor
- one `tool_kind`
- one test stack
- one exposure gate target

## Required implementation order

1. Confirm the slice file and rollout band.
2. Implement the semantic owner.
3. Implement the port seam.
4. Implement the adapter family.
5. Add the runtime entrypoint descriptor.
6. Add the shell-owned registry descriptor with `tool_kind`.
7. Add the runtime composition entrypoint.
8. Add unit, contract, adapter, integration, and architecture tests.
9. Update docs only for the exact slice and platform catalog.

## Required tests

- descriptor-shape test
- runtime-entrypoint-catalog test
- `tool_kind` validation test
- semantic unit tests
- port contract tests
- adapter tests
- integration tests through the shell-owned registry
- architecture boundary tests
- regression tests for existing Admin Band 0 and AWS slices

## Scope limits

- CTS-GIS is already implemented and remains the current spatial family root.
- AGRO-ERP starts after CTS-GIS follow-on approval.
- chronology work is mediation-first, not a `calendar` tool drop-in.
- host-alias work starts only after the hosted/network contracts land.
