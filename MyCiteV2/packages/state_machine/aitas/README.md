# AITAS

Authority: [../../../../docs/plans/v2-authority_stack.md](../../../../docs/plans/v2-authority_stack.md)

`packages/state_machine/aitas/` owns the MVP AITAS subset:

- `attention`
- `intention`

Time, archetype, and spatial expansion remain deferred until a later phase.

CTS-GIS now adds an additive tool-local AITAS layer in runtime payloads only:

- `attention_node_id`
- `intention_rule_id`
- `time_directive`
- `archetype_family_id`

That richer CTS-GIS-local layer does not widen the shared shell `AitasContext` validator. Shared shell AITAS remains attention/intention only.
