# Phase 06: Adapters

## purpose

Implement outward-facing port implementations without redefining core, shell, or domain meaning.

## source authorities

- [../v2-authority_stack.md](../v2-authority_stack.md)
- [../../contracts/import_rules.md](../../contracts/import_rules.md)
- [../../testing/architecture_boundary_checks.md](../../testing/architecture_boundary_checks.md)

## inputs

- stable ports
- stable inward contracts

## outputs

- `packages/adapters/*`
- adapter conformance tests

## prohibited shortcuts

- moving semantics into adapters
- direct tool-specific hacks inside general adapters
- instance-led hardcoding in reusable adapters

## required tests

- adapter loop
- architecture boundary loop

## completion gate

Adapters satisfy ports, keep outward details outward, and do not absorb semantic ownership.

## follow-on phase dependencies

- [07_tools.md](07_tools.md)
- [08_sandboxes.md](08_sandboxes.md)
- [09_runtime_composition.md](09_runtime_composition.md)
