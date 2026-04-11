# Terminology Usage Rules

Authority: [../plans/authority_stack.md](../plans/authority_stack.md)

## Rule

Every package-root README, module contract, phase doc, ADR, and migration doc must use glossary-defined terms only. See [../glossary/ontology_terms.md](../glossary/ontology_terms.md).

## Forbidden drift

- `MyCite2` as a normal v2 name
- `service layer` as a catch-all bucket
- `runtime service` as a substitute for `adapter` or `runtime composition`
- `tool shell` as a substitute for `tool attached through shell surface`
- `mediation` as a synonym for arbitrary UI logic

## Exception rule

Historical names may appear only when:

- quoting a v1 document title
- naming an existing v1 file or symbol
- documenting a drift pattern that v2 is preventing

The historical term must then be normalized back to the glossary term immediately.
