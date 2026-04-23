# Portal Shell Unification Plan Index

Date: 2026-04-23

Doc type: `index`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-04-23`

## Plan Set

| Order | File | Purpose | Hard dependencies | Retirement gates |
|---|---|---|---|---|
| 1 | `docs/plans/portal_shell_boundary_map_and_system_workbench_split_2026-04-23.md` | Freeze file ownership and clarify `SYSTEM` versus `workbench_ui` so follow-on slices do not drift across shell, runtime, and client layers. | None | Boundary assertions and split-specific tests land before runtime or renderer refactors begin. |
| 2 | `docs/plans/portal_shell_runtime_bundle_unification_2026-04-23.md` | Replace segmented shell bundle assembly with one shared runtime bundle contract and one shared envelope/composition path. | Boundary map | `portal_shell_runtime.py` no longer relies on open-coded per-surface assembly branching, and direct tool entrypoints reuse the shared assembly path. |
| 3 | `docs/plans/portal_shell_region_family_renderer_migration_2026-04-23.md` | Migrate control-panel, workbench, and interface-panel rendering to the canonical region families while shrinking compatibility branches. | Boundary map, runtime bundle plan stage 1 | Top-level client hosts stop using tool-identity branches as primary authority. Legacy `kind` and `interface_body` fields remain only behind explicit compatibility gates. |
| 4 | `docs/plans/portal_shell_unification_execution_plan_2026-04-23.md` | Define the stability-first merge order, limited parallelism rules, and closeout gates for the whole unification pass. | Boundary map, runtime bundle plan, renderer migration plan | Runtime and renderer compatibility branches retire in the documented order without touching public `inspector` alias retirement in this sequence. |

## Minimality Note

This is the smallest complete set that covers:

- the strict file-by-file boundary map
- runtime bundle assembly unification
- client renderer and region-family migration
- `SYSTEM` versus `workbench_ui` boundary clarification
- execution order and retirement gates

No separate plan was created for `SYSTEM` versus `workbench_ui` alone because the repo evidence shows that split is inseparable from the canonical boundary map and the tests that must enforce it.
