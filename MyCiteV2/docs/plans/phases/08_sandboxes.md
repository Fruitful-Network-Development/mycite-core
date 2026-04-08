# Phase 08: Sandboxes

## purpose

Implement orchestration boundaries for staged work, mediation context, and derived-artifact handling without owning domain semantics.

## source authorities

- [../authority_stack.md](../authority_stack.md)
- [../../ontology/interface_surfaces.md](../../ontology/interface_surfaces.md)
- [../../decisions/decision_record_0006_sandboxes_are_orchestration_boundaries.md](../../decisions/decision_record_0006_sandboxes_are_orchestration_boundaries.md)

## inputs

- state-machine contracts
- ports
- domain and cross-domain modules
- adapter implementations

## outputs

- `packages/sandboxes/*`
- sandbox orchestration tests

## prohibited shortcuts

- domain logic hidden in sandboxes
- shell ownership hidden in sandboxes
- datum truth moved into derived artifacts

## required tests

- sandbox loop
- architecture boundary loop

## completion gate

Sandboxes coordinate staging and mediation cleanly while remaining semantically subordinate to inward layers.

## follow-on phase dependencies

- [09_runtime_composition.md](09_runtime_composition.md)
- [10_integration_testing.md](10_integration_testing.md)
