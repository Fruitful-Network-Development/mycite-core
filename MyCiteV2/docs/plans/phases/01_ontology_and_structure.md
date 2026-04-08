# Phase 01: Ontology And Structure

## purpose

Fix v2 vocabulary, authority order, invariants, directory shape, and inert scaffolding before any implementation logic exists.

## source authorities

- [../authority_stack.md](../authority_stack.md)
- [../../ontology/structural_invariants.md](../../ontology/structural_invariants.md)
- [../../contracts/terminology_usage_rules.md](../../contracts/terminology_usage_rules.md)

## inputs

- v2 ontology docs
- initial ADR set
- v1 migration evidence

## outputs

- authoritative documentation scaffold
- inert package markers
- major-root contracts

## prohibited shortcuts

- adding working code
- copying v1 package shapes
- introducing undefined terminology

## required tests

- documentation consistency check
- major-root contract presence check
- naming drift scan

## completion gate

The scaffold answers authority order, allowed names, non-authoritative zones, build order, and prohibited shortcuts without chat context.

## follow-on phase dependencies

- [02_core_pure_modules.md](02_core_pure_modules.md)
