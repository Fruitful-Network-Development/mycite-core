# NIMM

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`packages/state_machine/nimm/` owns the MVP directive surface.

Implemented in this phase:

- one supported shell verb: `navigate`

Deferred in this phase:

- `investigate`
- `mediate`
- `manipulate`

CTS-GIS uses `nimm_directive` as an additive tool-local runtime label during the compatibility phase. That does not widen the shared shell directive contract; it remains CTS-GIS-local request/runtime state.
