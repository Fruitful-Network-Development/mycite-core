# Portal Shell Unification Plan Index

Date: 2026-04-23

Doc type: `index`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-23`

## Plan Set

| Order | File | Purpose | Hard dependencies | Retirement gates |
|---|---|---|---|---|
| 1 | `docs/plans/portal_shell_boundary_map_and_system_workbench_split_2026-04-23.md` | Freeze file ownership and clarify `SYSTEM` versus `workbench_ui` so follow-on slices do not drift across shell, runtime, and client layers. | None | Achieved: boundary assertions and split-specific tests landed before runtime or renderer refactors. |
| 2 | `docs/plans/portal_shell_runtime_bundle_unification_2026-04-23.md` | Replace segmented shell bundle assembly with one shared runtime bundle contract and one shared envelope/composition path. | Boundary map | Achieved for shell-unification scope: direct tool entrypoints reuse the shared shell path; remaining root/helper cleanup is non-blocking and separate. |
| 3 | `docs/plans/portal_shell_region_family_renderer_migration_2026-04-23.md` | Migrate control-panel, workbench, and interface-panel rendering to the canonical region families and close out tool-specific host branching. | Boundary map, runtime bundle plan stage 1 | Achieved: top-level client hosts use canonical family authority, and active runtime/client paths stay inside the three canonical region families. |
| 4 | `docs/plans/portal_shell_unification_execution_plan_2026-04-23.md` | Define the stability-first merge order, limited parallelism rules, and closeout gates for the whole unification pass. | Boundary map, runtime bundle plan, renderer migration plan | Achieved: the sequence closed out in the documented order without touching public `inspector` alias retirement. |

## Minimality Note

This is the smallest complete set that covers:

- the strict file-by-file boundary map
- runtime bundle assembly unification
- client renderer and region-family migration
- `SYSTEM` versus `workbench_ui` boundary clarification
- execution order and retirement gates

No separate plan was created for `SYSTEM` versus `workbench_ui` alone because the repo evidence shows that split is inseparable from the canonical boundary map and the tests that must enforce it.

## Closeout Note

This plan set is complete for shell unification. It remains in `docs/plans/` as the closeout record for the canonical family-contract migration and the active three-family shell model.
