# MVP End-To-End Slice

Authority: [authority_stack.md](authority_stack.md)

## Slice name

Shell Action To Local Audit

## Exact slice claim

One runtime composition path accepts a serialized shell action over a canonical datum-ref subject, reduces that action through pure shell-state logic, persists a normalized local-audit record through an explicit audit port and filesystem adapter, and returns the resulting shell state plus persisted audit metadata.

## Included layers in order

1. `packages/core/datum_refs`
2. `packages/state_machine/aitas`
3. `packages/state_machine/nimm`
4. `packages/state_machine/hanus_shell`
5. `packages/ports/audit_log`
6. `packages/modules/cross_domain/local_audit`
7. `packages/adapters/filesystem`
8. `instances/_shared/runtime`

## Runtime interaction

The runtime path does exactly this:

1. receive input payload with:
   - shell action type
   - shell verb
   - focus subject
2. normalize the focus subject as a canonical datum-ref
3. reduce shell state to the next normalized state
4. create a local-audit event describing the accepted transition
5. persist the event through the `audit_log` contract
6. read back the persisted metadata needed for the response
7. return one response payload with:
   - normalized subject
   - normalized verb
   - normalized shell state
   - persisted audit path or identifier
   - persisted audit timestamp

## Why this slice

This slice is the smallest one that still traverses enough layers to prove the architecture:

- core is used
- state_machine is used
- a port is used
- a recreated module is used
- an adapter is used
- runtime composition is used
- integration and architecture-boundary checks are meaningful

## Forbidden additions inside this slice

- no tool dispatch
- no sandbox orchestration
- no external-events behavior
- no second adapter
- no second runtime path
- no domain module participation
