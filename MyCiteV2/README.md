# MyCiteV2

MyCiteV2 is a documentation-first program space for rebuilding MyCite correctly from scratch. It is not a partial port of v1, not a compatibility mirror, and not a place for opportunistic feature work before the ontology, authority model, dependency direction, and build order are explicit.

Start with [docs/plans/authority_stack.md](docs/plans/authority_stack.md). That file defines the precedence order for all v2 decisions.

## What v2 is

- An architecture-led scaffold that externalizes structural invariants, phase order, import boundaries, and migration reasoning.
- A low-drift surface for future agents to read before writing code.
- A place where v1 is treated as evidence, not as a package template.

## What v2 is not

- Not an in-progress rewrite of v1 modules.
- Not a place to copy `mycite_core/`, `packages/hosts/`, or instance-led paths into new shapes.
- Not a second authority surface beside the docs in this tree.

## How to navigate this tree

- Read [docs/plans/authority_stack.md](docs/plans/authority_stack.md).
- Read [docs/ontology/structural_invariants.md](docs/ontology/structural_invariants.md).
- Read [docs/decisions/README.md](docs/decisions/README.md).
- Read [docs/plans/master_build_sequence.md](docs/plans/master_build_sequence.md).
- Use [docs/plans/v1-migration/README.md](docs/plans/v1-migration/README.md) only after the v2 ontology is clear.

## Working rules

- Use glossary-defined terms only. See [docs/glossary/ontology_terms.md](docs/glossary/ontology_terms.md).
- Do not infer architecture from v1 path names.
- Do not implement beyond inert scaffolding during the scaffold phase. See [docs/plans/implementation_prohibition_for_scaffold_phase.md](docs/plans/implementation_prohibition_for_scaffold_phase.md).
- Do not treat `docs/wiki/` or `docs/audits/` as authority. See [docs/ontology/non_authoritative_zones.md](docs/ontology/non_authoritative_zones.md).

## Directory intent

- `docs/` holds the authoritative v2 ontology, decisions, plans, and enforcement rules.
- `packages/` holds inert package placeholders only.
- `instances/` holds runtime composition placeholders only. It is not an instance-led architecture surface.
- `tests/` holds planned test-loop placeholders only.
