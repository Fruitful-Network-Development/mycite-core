# Authority Stack

This file is the single precedence source for MyCiteV2 docs and planning.

Lifecycle, registry, and reading-path governance live under
[../governance/](../governance/). Those documents manage discoverability and
cleanup, but they do not replace the semantic precedence defined here.

## Precedence order

1. [../ontology/structural_invariants.md](../ontology/structural_invariants.md) and the ontology files it governs
2. [../decisions/](../decisions/)
3. [phases/](phases/), [v2-master_build_sequence.md](v2-master_build_sequence.md), and [v2-phase_completion_definition.md](v2-phase_completion_definition.md)
4. active V2 rollout and cutover planning under [post_mvp_rollout/](post_mvp_rollout/)
5. [../contracts/](../contracts/) and [../testing/](../testing/) as enforcement surfaces for approved structure
6. [version-migration/](version-migration/) for V1 evidence, recreation guidance, and retirement review
7. [../records/](../records/) for completed implementation evidence
8. [legacy/](legacy/), [../contracts/legacy/](../contracts/legacy/), [../wiki/legacy/](../wiki/legacy/), [../wiki/](../wiki/), and [../audits/](../audits/) as lower-precedence historical or secondary evidence
9. repo code under `MyCiteV2/` and `MyCiteV1/`, with deployed runtime state outside the repo always subordinate to repo docs and repo-owned code

## Resolution rule

When two sources conflict, the higher-precedence source wins. The lower source
must be updated, annotated, or ignored.

## Normalization rule

If a current document still uses the unprefixed authority-stack path, the
unprefixed phase-completion path, the older migration-root name, or an old V1
docs path, treat that as stale naming drift and normalize it to:

- `v2-authority_stack.md`
- `v2-phase_completion_definition.md`
- `version-migration/`
- `docs/*/legacy/` or `docs/records/`, depending on purpose

## Required links

This file must be linked from:

- `docs/README.md`
- `docs/governance/README.md`
- `docs/governance/reading_paths.md`
- `docs/plans/README.md`
- `MyCiteV2/README.md`
- every major-root `README.md`
- `docs/contracts/module_contract_template.md`
- current planning indexes and major post-MVP planning roots
