# NIMM

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`packages/state_machine/nimm/` owns the directive schema and mutation contract foundation.

Implemented:

- versioned directive schema: `mycite.v2.nimm.directive.v1`
- canonical verbs: `navigate`, `investigate`, `mediate`, `manipulate`
- target-address structure for file/datum/object addressing
- envelope schema: `mycite.v2.nimm.envelope.v1` (directive + AITAS context)
- staging compiler (`StagingArea`) that produces manipulation directives
- mutation contract endpoint/action constants and runtime handler interface
- verb handler surface with explicit deferred stubs:
  - `handle_nimm_investigate`
  - `handle_nimm_mediate`
  - `handle_nimm_manipulate`

Deferred:

- tool-specific runtime semantics for non-navigation verbs
- full multi-tool mutation orchestration handlers

CTS-GIS uses `nimm_directive` as an additive tool-local runtime label during the compatibility phase. That does not widen the shared shell directive contract; it remains CTS-GIS-local request/runtime state.
