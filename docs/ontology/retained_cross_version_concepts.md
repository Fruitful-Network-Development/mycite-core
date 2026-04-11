# Retained Cross-Version Concepts

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file records which concepts survive from V1 into V2 as concepts, and where
V2 now places them. It exists to prevent two opposite mistakes:

- deleting real concepts just because they were explained first in V1
- copying V1 package shapes into V2 just because the concept still matters

## Where precise documentation belongs

- Put cross-version structural truths in `docs/ontology/`.
- Put enforceable ownership and boundary rules in `docs/contracts/`.
- Put unfinished work only in `docs/plans/`.
- Put completed implementation history in `docs/records/`.
- Keep legacy-only behavior and historical explanation in `docs/*/legacy/`.

## Retained concepts

| Concept | What survives | V1 evidence | V2 home |
| --- | --- | --- | --- |
| Hanus interface surface | The shell-facing interaction model and serialized legality surface survive as concepts. | `docs/plans/legacy/v1-hanus_interface_model.md`, `docs/wiki/legacy/architecture/system-state-machine.md` | `MyCiteV2/packages/state_machine/`, `docs/plans/phases/03_state_machine_and_hanus_shell.md` |
| AITAS and NIMM | The state-machine vocabulary survives. | `docs/wiki/legacy/architecture/aitas-context.md`, `docs/wiki/legacy/Glossary.md` | `MyCiteV2/packages/state_machine/`, `docs/glossary/ontology_terms.md` |
| Tools attach through shell surfaces | Tools remain shell-attached providers rather than alternate shells. | `docs/plans/legacy/v1-tool_dev.md`, `MyCiteV1/packages/tools/README.md` | `docs/decisions/decision_record_0004_tools_attach_through_shell_surfaces.md`, `MyCiteV2/packages/tools/`, `docs/contracts/tool_state_and_datum_authority.md` |
| Datum authority vs utility state | Explicit datum truth remains separate from convenience files and derived artifacts. | `docs/plans/legacy/v1-tool_dev.md`, `docs/contracts/legacy/data_engine.md`, `MyCiteV1/packages/tools/README.md` | `docs/ontology/structural_invariants.md`, `docs/contracts/tool_state_and_datum_authority.md` |
| Runtime composition vs semantic ownership | Host/runtime composition remains separate from shell, domain, and tool semantics. | `docs/plans/legacy/modularity/ownership-boundary.md`, `docs/plans/legacy/modularity/runtime_alignment_report.md` | `docs/decisions/decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md`, `docs/contracts/repo_and_runtime_boundary.md`, `MyCiteV2/instances/_shared/` |
| MSS | Compact-array scoped context remains a real concept even when not fully reopened in MVP. | `docs/wiki/legacy/contracts-mss/` | `MyCiteV2/packages/core/` plus future ports/modules that reopen contract-context behavior |
| SAMRAS | Shape-addressed structural modeling remains a retained core concept. | `docs/wiki/legacy/samras/` | `MyCiteV2/packages/core/` and future structure-facing contracts |
| HOPS | Fixed homogeneous ordinal partition modeling remains a retained core concept. | `docs/wiki/legacy/hops/homogeneous_ordinal_partition_structure.md` | `MyCiteV2/packages/core/` and future time-projection seams |

## Transition rule

When a concept survives from V1 into V2:

- keep the concept
- rewrite the owner and boundary in V2 terms
- do not copy the V1 package layout, route shape, or runtime tree

## Promotion rule

If a retained concept is still explained best in `docs/*/legacy/`, promote only
the concept and its current owner. Do not promote:

- V1 route catalogs
- V1 filesystem inventories
- V1 page-model wording
- V1 package or runtime shapes
