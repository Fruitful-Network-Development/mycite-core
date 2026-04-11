# Phase 02: Core Pure Modules

## purpose

Recreate pure core structures and utilities that do not depend on shell, runtime, adapters, or tools.

## source authorities

- [../v2-authority_stack.md](../v2-authority_stack.md)
- [../../ontology/dependency_direction.md](../../ontology/dependency_direction.md)
- [../v1-migration/source_authority_index.md](../v1-migration/source_authority_index.md)

## inputs

- phase 01 scaffold
- v1 evidence for datum refs, identities, HOPS, SAMRAS, MSS, and crypto splits

## outputs

- pure `packages/core/*` modules
- unit tests for deterministic behavior

## prohibited shortcuts

- importing runtime helpers
- importing state-machine or sandbox logic
- reviving `vault_session` as one module

## required tests

- pure unit loop
- architecture boundary loop for core

## completion gate

All core modules are deterministic, inward-only, and free of runtime, tool, adapter, and instance-path imports.

## follow-on phase dependencies

- [03_state_machine_and_hanus_shell.md](03_state_machine_and_hanus_shell.md)
- [04_ports.md](04_ports.md)
