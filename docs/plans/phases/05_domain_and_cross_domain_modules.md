# Phase 05: Domain And Cross-Domain Modules

## purpose

Recreate domain semantics and cross-domain semantics without collapsing them into a broad service bucket.

## source authorities

- [../v2-authority_stack.md](../v2-authority_stack.md)
- [../../ontology/structural_invariants.md](../../ontology/structural_invariants.md)
- [../version-migration/v1_retention_vs_recreation.md](../version-migration/v1_retention_vs_recreation.md)

## inputs

- core modules
- state-machine contracts where needed
- ports

## outputs

- `packages/modules/domains/*`
- `packages/modules/cross_domain/*`
- module-level tests

## prohibited shortcuts

- recreating `services/` as a catch-all
- reviving `vault_session` as one module
- importing adapters or instances

## required tests

- pure unit loop
- contract loop
- architecture boundary loop

## completion gate

Each module has narrow ownership, explicit inputs and outputs, and no broad service-shaped dumping ground exists.

## follow-on phase dependencies

- [06_adapters.md](06_adapters.md)
- [08_sandboxes.md](08_sandboxes.md)
