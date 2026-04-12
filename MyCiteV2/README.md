# MyCiteV2

MyCiteV2 is the modular V2 code root. The authoritative semantics still live in
`../docs/`; this tree is the corresponding implementation surface for the V2
portal host, runtime, packages, and tests.

Start with [../docs/plans/v2-authority_stack.md](../docs/plans/v2-authority_stack.md). That file defines the precedence order for all v2 decisions.

## What v2 is

- A docs-first but implemented modular codebase for the current V2 portal.
- A place where V1 concepts are recreated under clarified ownership and
  dependency rules.
- A low-drift surface where ports, adapters, state-machine logic, runtime
  composition, and host transport stay separated.

## What v2 is not

- Not a V1 parity mirror.
- Not a place to copy old root paths or let deployment topology define
  semantics.
- Not a second documentation authority beside `../docs/`.

## How to navigate this tree

- Read [../docs/README.md](../docs/README.md).
- Read [../docs/plans/v2-authority_stack.md](../docs/plans/v2-authority_stack.md).
- Read [../docs/governance/README.md](../docs/governance/README.md).
- Read [../docs/governance/reading_paths.md](../docs/governance/reading_paths.md).
- Read [../docs/contracts/v2_surface_ownership_map.md](../docs/contracts/v2_surface_ownership_map.md).
- Read [../docs/ontology/structural_invariants.md](../docs/ontology/structural_invariants.md).
- Read [../docs/ontology/retained_cross_version_concepts.md](../docs/ontology/retained_cross_version_concepts.md).
- Read [../docs/decisions/README.md](../docs/decisions/README.md).
- Read [../docs/plans/post_mvp_rollout/current_planning_index.md](../docs/plans/post_mvp_rollout/current_planning_index.md) for current rollout and hardening work.
- Read [../docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md](../docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md) if the work touches live deployment, repo clarity, or V1 retirement.
- Use [../docs/plans/version-migration/README.md](../docs/plans/version-migration/README.md) for V1 evidence and retirement review, not as the active live cutover queue.
- Use [../docs/records/README.md](../docs/records/README.md) for completed work.
- Use [../docs/personal_notes/README.md](../docs/personal_notes/README.md) only for preserved non-authoritative notes and archived discussions.

## Working rules

- Use glossary-defined terms only. See [../docs/glossary/ontology_terms.md](../docs/glossary/ontology_terms.md).
- Do not infer architecture from v1 path names.
- Treat scaffold-phase prohibition docs as historical phase guidance, not as a claim that V2 is still scaffold-only.
- Do not treat `docs/wiki/` or `docs/audits/` as authority. See [../docs/ontology/non_authoritative_zones.md](../docs/ontology/non_authoritative_zones.md).
- Do not treat `docs/personal_notes/` as authority. See [../docs/ontology/non_authoritative_zones.md](../docs/ontology/non_authoritative_zones.md).

## Directory intent

- `../docs/` holds the authoritative v2 ontology, decisions, plans, contracts, and completion records.
- `instances/_shared/portal_host/` holds the V2-native portal host and shell assets.
- `instances/_shared/runtime/` holds shared runtime composition and entrypoint catalogs.
- `packages/` holds the modular V2 layers plus any still-unimplemented placeholder subpackages.
- `tests/` holds implemented boundary-loop verification suites.
