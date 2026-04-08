# Phase 04: Ports

## purpose

Define explicit capability seams for external storage, eventing, projection, and shell-facing interactions.

## source authorities

- [../authority_stack.md](../authority_stack.md)
- [../../contracts/import_rules.md](../../contracts/import_rules.md)
- [../v1-migration/mycite_v2_structure_report.md](../v1-migration/mycite_v2_structure_report.md)

## inputs

- core modules
- state-machine contracts
- v1 evidence of mixed reusable/runtime imports

## outputs

- `packages/ports/*`
- explicit interface contracts

## prohibited shortcuts

- adapter code inside ports
- host path math inside ports
- treating helper imports as implicit interfaces

## required tests

- contract loop for port interfaces
- architecture boundary loop for port purity

## completion gate

Every required external seam is named as a port and no port contains adapter logic or runtime path assumptions.

## follow-on phase dependencies

- [05_domain_and_cross_domain_modules.md](05_domain_and_cross_domain_modules.md)
- [06_adapters.md](06_adapters.md)
