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
- one test stack
- one exposure gate target

## Required implementation order

1. Confirm the slice file and rollout band.
2. Implement the semantic owner.
3. Implement the port seam.
4. Implement the adapter family.
5. Add the runtime entrypoint descriptor.
6. Add the shell-owned registry descriptor.
7. Add the runtime composition entrypoint.
8. Add unit, contract, adapter, integration, and architecture tests.
9. Update docs only for the exact slice and platform catalog.

## Required tests

- descriptor-shape test
- runtime-entrypoint-catalog test
- semantic unit tests
- port contract tests
- adapter tests
- integration tests through the shell-owned registry
- architecture boundary tests
- regression tests for existing Admin Band 0 and AWS slices

## Scope limits

- Maps starts after this platform pass, not during it.
- AGRO-ERP starts after Maps.
- PayPal, analytics, progeny, workbench, and sandboxes remain outside this track until explicitly approved.
