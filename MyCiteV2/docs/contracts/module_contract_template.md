# Module Contract Template

Use this template for any future module contract. Terms must come from [../glossary/ontology_terms.md](../glossary/ontology_terms.md). Authority order is defined in [../plans/authority_stack.md](../plans/authority_stack.md).

## Purpose

State what the module owns in one sentence.

## Owns

- Explicit list of semantic responsibilities.

## Does Not Own

- Explicit list of nearby concerns this module must not absorb.

## Inputs

- Named upstream contracts or state surfaces only.

## Outputs

- Named contracts, projections, or derived artifacts only.

## Allowed Dependencies

- List only approved inward dependencies.

## Forbidden Dependencies

- List outward layers, host code, tool code, instance paths, and other forbidden surfaces.

## Test Scope

- Unit checks
- Boundary checks
- Contract checks

## Source Authorities

- Link the controlling v2 ontology, ADRs, phase docs, and migration docs in precedence order.
