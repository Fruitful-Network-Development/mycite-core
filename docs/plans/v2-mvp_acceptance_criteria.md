# MVP Acceptance Criteria

Authority: [v2-authority_stack.md](v2-authority_stack.md)

The MVP passes only if all of the following are true.

## Functional acceptance

1. a runtime can receive a serialized shell action containing:
   - one canonical datum-ref subject
   - one supported shell verb
2. the subject is normalized by `packages/core/datum_refs`
3. the shell action is reduced by `packages/state_machine`
4. a normalized local-audit event is produced
5. the event is persisted and read back through the `audit_log` port and filesystem adapter
6. the runtime returns one normalized result containing:
   - shell state
   - normalized subject
   - verb
   - persisted audit metadata

## Boundary acceptance

1. `packages/core` uses no runtime helpers, adapters, tools, sandboxes, or instance paths
2. `packages/state_machine` imports no tools, adapters, sandboxes, or instances
3. `packages/modules/cross_domain/local_audit` imports no runtime helpers or instances
4. `packages/ports/audit_log` contains no adapter logic
5. `packages/adapters/filesystem` owns no shell or module semantics
6. `instances/_shared/runtime` composes but does not redefine inward behavior

## Test acceptance

1. pure unit loop passes
2. state machine loop passes
3. port/contract loop passes
4. adapter loop passes
5. integration loop passes for the chosen slice
6. architecture boundary loop passes for all included layers

## Scope acceptance

The MVP fails scope acceptance if any of these appear:

- tool implementation
- sandbox implementation
- domain-module implementation
- second adapter family
- second runtime composition path
- flavor expansion
- HOPS, SAMRAS, MSS, or crypto work not required by the chosen slice
