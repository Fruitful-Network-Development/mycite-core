# Phase 03: State Machine And Hanus Shell

## purpose

Define the serialized shell state, AITAS vocabulary, NIMM directives, and mediation surface behavior independently of tools and hosts.

## source authorities

- [../authority_stack.md](../authority_stack.md)
- [../../ontology/interface_surfaces.md](../../ontology/interface_surfaces.md)
- [../v1-migration/hanus_interface_analysis.md](../v1-migration/hanus_interface_analysis.md)
- [../../../../docs/plans/hanus_interface_model.md](../../../../docs/plans/hanus_interface_model.md)

## inputs

- core pure modules
- v2 glossary
- v1 Hanus and AITAS evidence

## outputs

- `packages/state_machine/*`
- serialized state contracts
- shell legality tests

## prohibited shortcuts

- importing tool code
- importing host code
- burying shell meaning in UI or adapter code

## required tests

- pure unit loop for state transitions
- contract loop for state payload shapes
- architecture boundary loop for shell ownership

## completion gate

Shell legality, attention, intention, directives, and mediation surface behavior are explicit, serializable, and tool-independent.

## follow-on phase dependencies

- [04_ports.md](04_ports.md)
- [07_tools.md](07_tools.md)
- [08_sandboxes.md](08_sandboxes.md)
