# Further Recoord and writtings:

## PROMPT 1:





Considering that my main concerns are making sure the MOS paradigm of data is highly accurate, robust and reflective of the deign I have meticulously created, as well as the transition of data access to use the peripheral data route for tool and portal interfacing surfaces, help navigate these plan question provided my CODEX in response to my prompt. I was thinking my goal for this round of planning, I would externalize as much of the planning to be precise as possible allowing for easy and quick cut-over.

PROMPT:
Help me externalize the staging for seeing out and planning the cut over deffined by the contents of [mos_sql_backed_core_declaration_draft.md](repo/mycite-core/docs/personal_notes/MOS/mos_sql_backed_core_declaration_draft.md) .
Also see [datum_logic_area_investigation_clarity.md](repo/mycite-core/docs/personal_notes/archive/MOS/datum_logic_area_investigation_clarity.md) , [data_base_use_findings.md](repo/mycite-core/docs/personal_notes/MOS/data_base_use_findings.md) , [mos_novelty_definition.md](repo/mycite-core/docs/personal_notes/MOS/mos_novelty_definition.md) , and [mycelial_ontological_schema.md](repo/mycite-core/docs/personal_notes/MOS/mycelial_ontological_schema.md) .

I want to properly plan and have a hard, stable unification of logic defined and planned.
Consider the contents, reffeences and conceptual materialization that will fuel the creation go the master plan to be made in [master_plan_mos.md](repo/mycite-core/docs/plans/master_plan_mos.md) , as well as the other plan files and audit files.
Consider the use of yaml file workflow to increase the effectiveness of this master plan, although don't be too strict with YAML as it can create dependencies that don't allow for new approaches to problems or consideration that arrise.

QUESTIONS(I'd prefer precision of language that answer each question for answer `4` so that precision language can optimize outcome and quickness of effective planning.):

What should the MOS master plan optimize  for first?

1. Dual Track: Run a v1 operational SQL cut-over track now with separate gated standardization work for unresolved MOS semantics.

2. V1 Cut-over Only: Focus the plan on shipping the SQL backed core and defer broader MOS standardization to later docs.

3. Full MOS closure: Make the master plan solve v1 cut-over and unresolved  native MOS semantics in one unified program.

How much authority should YAML have in the MOS planning workflow?

1.) companion index: Markdown plans stay authoritative; YAML tracks tasks, gates, dependencies, and evidence links.

2.) Equal Authority: Markdown and YAML are co-maintained as parallel sources of truth for plan state and execution of tasks

3.) Minimal YEML: Use YAML only sparingly for a dew checklists ro machine-readable task bundles

How should NIMM/AITAS and broader directive-context ideas be handled in the master plan?

1.) Future track: Keep them explicitly out of the v1 SQLcitover and stage  them as later widening track.

2.) keep them out of the cut-over path but include a parallel design /spec track in the same master plan

3.) Core to V1: Treat directive-context unification as part of the v1 core cut-over definition.

I prefer answer in more precise language semi-Full MOS closure,  companion index, large plan archetture that includes Core to V1

---


## OUTPUT 1 ~ Staged closure for v1 and semantics

Your own SQL‑backed core draft acknowledges that there is enough information to build a functional SQL authority adapter and datum store, but not enough for a complete native MOS standard because the missing pieces involve core identity and mutation semantics. Separate audits confirm that key algorithms—MSS hashing, hyphae derivation, deterministic edit rules and directive models—are undefined. The master plan should therefore optimise for delivering the v1 cut‑over while closing these semantic gaps in parallel. Use a single plan that runs the SQL migration and adapter work as its primary track but includes gated tasks to specify and implement the unresolved semantics. In short: build the operational SQL core now and place unresolved MOS semantics on an immediately adjacent track with explicit milestones rather than deferring them indefinitely.

YAML should act as a companion index rather than a co‑equal authority. Keep the canonical plan, rationale and design decisions in Markdown and use YAML to record tasks, gates, dependencies and evidence links. This balances human readability with machine‑readability and avoids over‑formalising the planning process. The schema notes suggest YAML can optimise agent workflows but such configuration is optional; treating YAML as an index preserves flexibility.

Handle NIMM/AITAS and other directive‑context ideas as a parallel design/spec track. These directive models are not part of the current core, so do not block the v1 SQL cut‑over on them. Instead, include a section in the master plan that outlines how directive‑context unification will be designed and integrated in a future phase. This keeps the core migration clean while ensuring the broader architecture will eventually absorb directive‑context logic.

---


## PROMPT 2

Consider the currnet plan.
> `master_plan_mos.md`

---


## OUTPUT 2 ~ Review of MOS Master Plan

The uploaded document lays out a coherent programme for migrating to a SQL-backed core while acknowledging that many MOS semantics remain unresolved. It proposes treating “master_plan_mos.md” as the single authoritative document, organised into three tracks: v1 SQL cutover, semantic-closure gating tasks, and a parallel design/spec track for future NIMM/AITAS work. The plan emphasises that v1 should focus on operational SQL authority (anthology and document reads, contracts and grants, audit append, tool exposure) without assuming problems like MSS hashing, hyphae derivation or deterministic edit logic have been solved. A companion YAML index is recommended for task tracking, but Markdown remains the canonical source. Overall, the plan provides a structured path to begin the SQL migration while keeping open issues clearly gated, and it aligns with the earlier guidance to externalize planning details and avoid conflating cutover with full MOS closure.

---


## INPUT 3

Consider the updated repo the given output (Return me the precision prompt for completing):
Implemented the MOS program as repo documentation in [master_plan_mos.md](/srv/repo/mycite-core/docs/plans/master_plan_mos.md), added the companion index at [master_plan_mos.index.yaml](/srv/repo/mycite-core/docs/plans/master_plan_mos.index.yaml), and registered both in [docs/plans/README.md](/srv/repo/mycite-core/docs/plans/README.md). The master plan now includes the authority matrix, cutover scope table, Track A/B/C structure, semantic gates `SG-1` through `SG-4`, interface rules, validation gates, risks, and exit criteria, with Markdown explicitly declared as the authoritative source.

I also kept the “one master doc” rule intact, so I did not create a competing `masterplan_mos.md`. Verification-wise, I checked the rendered content and parsed the YAML successfully with `python3`, so the companion index is syntactically valid.

---


## OUTPUT 3

> **“Follow the newly created master plan in `docs/plans/master_plan_mos.md` and its companion index `docs/plans/master_plan_mos.index.yaml` to execute the cut-over program. Treat `master_plan_mos.md` as the authoritative source of tasks and proceed with Track A’s phased SQL migration:**

**Precision Prompt:**

> “Open the `master_plan_mos.md` in the `/srv/repo/mycite-core/docs/plans/` directory and confirm that it contains the authority matrix, cutover scope table, the Track A/B/C structure, semantic gates SG‑1 to SG‑4, interface rules, validation gates, risks and exit criteria. Then check `master_plan_mos.index.yaml` in the same directory for syntactical validity against its YAML schema. Finally, verify that `docs/plans/README.md` references both files and that no duplicate file (such as `masterplan_mos.md`) exists. Report any missing elements or inconsistencies.”
> *Phase 0*: Consolidate and publish the authority matrix, cutover scope table, and semantic gap register.
> *Phase 1*: Define the v1 SQL authority surface covering anthology/document reads, contract/reference-resolution metadata, audit/event append, portal grants, and tool exposure/config.
> *Phase 2*: Implement shadow‑mode SQL adapters behind existing datum‑store and runtime seams without changing file/workbench‑oriented behavior.
> *Phase 3*: Run parity tests and readiness gates with the filesystem adapters, ensuring rollback capability.
> *Phase 4*: Promote SQL-backed adapters to primary authority for the approved surfaces.
> *Phase 5*: Remove FND capability defaults only once DB grants replicate the same posture.
>
> Simultaneously register the unresolved semantic tasks under Track B’s gates (SG‑1: version identity/MSS hashing, SG‑2: hyphae derivation, SG‑3: deterministic edit/remap, SG‑4: standard closure criteria) and begin design work on NIMM/AITAS as Track C. Use the YAML index to log task status, dependencies, gates, and evidence. Keep Markdown as the canonical source for rules and rationale and avoid creating parallel master-plan documents.”

---


## INPUT 4

Consider the updated repo and the given output. Return me the precision prompt to have the agent proceed in completing the plan:

Track B is now closed in the repo. The SQL datum-store gained a new semantic layer in [datum_semantics.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/sql/datum_semantics.py:11) and [datum_store.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/sql/datum_store.py:106): `mos.mss_sha256_v1` document version identity, `mos.hyphae_chain_v1` row semantic identity with the `0-0-*` rudi-prefix rule, and bounded SG-3 preview/apply helpers for insert, delete, and move. The mutation policy is intentionally strict: live-reference deletes are refused, and hyphen-qualified local refs stay compatibility-only for mutation safety. Portal/runtime seams were left unchanged; the new behavior stays behind the SQL datum-store boundary.

The program artifacts are synchronized. [master_plan_mos.md](/srv/repo/mycite-core/docs/plans/master_plan_mos.md:41) now records the closure pass, [master_plan_mos.index.yaml](/srv/repo/mycite-core/docs/plans/master_plan_mos.index.yaml:128) marks `SG-1` through `SG-4` and `C1` completed, [mos_semantic_gate_register_2026-04-21.md](/srv/repo/mycite-core/docs/plans/mos_semantic_gate_register_2026-04-21.md:28) is now a closed gate ledger, and [mos_directive_context_design_track_2026-04-21.md](/srv/repo/mycite-core/docs/plans/mos_directive_context_design_track_2026-04-21.md:29) now defines Track C scope, schema candidates, update policy, and SQL-core binding points. I also added dedicated closure artifacts for each gate in `docs/plans/mos_sg*_2026-04-21.md` and appended the Track B closure addendum to [mos_sql_cutover_execution_report_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_sql_cutover_execution_report_2026-04-21.md:113).

Verification passed: `69` targeted tests green across the SQL adapters, runtime/cutover regressions, and the new semantic/mutation cases, and the YAML companion parsed cleanly with `MOS-SG1` through `MOS-SG4` plus `MOS-C1` resolving to `completed`.

---


## OUTPUT 4

Here is a precise prompt you can give the Codex agent to complete the remaining MOS program work:

> **“Proceed with the MOS program beyond Track B. Follow the directive‑context design in `mos_directive_context_design_track_2026-04-21.md` to implement Track C without blocking the SQL cutover. Create SQL tables and adapters for `directive_context_snapshots` and `directive_context_events`, keyed by `version_hash` and `hyphae_hash`, reflecting the semantic overlay model. Add contracts, tests and runtime seams so that the SQL-backed core can read normalized directive overlays and compose them with authoritative datum semantics where approved, but never mutate the datum rows themselves. Update `master_plan_mos.md` and `master_plan_mos.index.yaml` with progress, evidence and any new validation gates, and produce closure artifacts for Track C. Ensure the cutover path remains stable and non‑blocking, preserving file/workbench behaviour and keeping directive context a parallel design track as described.”

---

## INPUT 5

Consider the updated repo and the given output:

Track C is now implemented as a non-blocking, read-only directive-overlay path. The new port lives in [contracts.py](/srv/repo/mycite-core/MyCiteV2/packages/ports/directive_context/contracts.py), the SQL schema and adapter are in [_sqlite.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/sql/_sqlite.py) and [directive_context.py](/srv/repo/mycite-core/MyCiteV2/packages/adapters/sql/directive_context.py), and the approved runtime seam is in [portal_system_workspace_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py). The SQL-backed core can now read normalized `directive_context_snapshots` and append/read `directive_context_events` by `version_hash` and `hyphae_hash`, then compose overlays into the system workspace without ever mutating authoritative datum rows or changing file/workbench behavior.
The MOS program artifacts are synced as well: [master_plan_mos.md](/srv/repo/mycite-core/docs/plans/master_plan_mos.md) now records the Track C overlay pass and its new non-mutation validation gate, [master_plan_mos.index.yaml](/srv/repo/mycite-core/docs/plans/master_plan_mos.index.yaml) now tracks the implementation as `MOS-C2`, [mos_directive_context_design_track_2026-04-21.md](/srv/repo/mycite-core/docs/plans/mos_directive_context_design_track_2026-04-21.md) reflects the implemented schema/runtime posture, and [mos_track_c_directive_context_overlay_closure_2026-04-21.md](/srv/repo/mycite-core/docs/plans/mos_track_c_directive_context_overlay_closure_2026-04-21.md) serves as the closure artifact.
Verification passed: `py_compile` on the new Track C modules, YAML parse of `master_plan_mos.index.yaml`, and `77` regression tests green across the SQL adapters, directive-context contracts, runtime composition, and existing filesystem/runtime paths.

Return me the precision prompt to have the agent proceed in completing the plan.
The resulting pass needs to complete loose ends and have the agent plan out the plans and audits to be completed for further comprehensive review of all data from the fnd portal repo copy to ensure its thoroughly combed over for alignment to the new paradigm.
This should proceed ingesting the data in the new MOS backed database with the newly defined convention.
This should allow for a complete switch over to the new portal paradigm and the removal of legacy code, documentation ect. Thus completing the cut over. Instruct the agent to additional comprehensively audit the documentation to ensure the everything is robustly represented.

Lastly review the visualization so that the result is a more clear datum file workbench by enabling the use of a data base using and backed UI/tool interface surface for the use of a script based tool interface surface.
It should be clear cut and utilitarian, akin to google sheets/excel type programs. Starting minimal is best. Hardening and simplification for a utilitarian reflective content and controls for the control panel.
Make sure the tool interface surface is sturdy and investigated for good design modularization and reflective of what is meant to be a materialization of a script grounded interface surface.
The lynch pin of this part of the consolidation simplification is having a better tool interfaces by making sure the the visualization of the state and output for mediation (with respect to sources) can be made less heavy and less developmentally intensive by have it now backed by the data base usage and a script based tool interface surface.

---


## OUTPUT ~ Final cut‑over and UI consolidation

To finish the MOS program, use this precision prompt to instruct your Codex agent:

> **“Complete the MOS cut‑over by ingesting the FND portal repository into the SQL‑backed datum store and replacing all filesystem authority.**
> **Ingestion:** Write a migration script to traverse the FND portal repo copy, compute `version_hash` and `hyphae_hash` for each datum document, insert the rows into the MOS database via `datum_store` and `datum_semantics`, and record any `directive_context_events` needed to preserve tool‑local overlays. Verify no legacy rows remain unaccounted for.
> **Legacy removal:** Remove the old filesystem‑backed adapters, data, and documentation once ingestion is complete and update `master_plan_mos.md` and `master_plan_mos.index.yaml` to mark the cut‑over and document removals.
> **Comprehensive audits:** Draft and execute final audits to confirm that all data from the FND copy align with the new MOS conventions. Generate audit reports under `docs/audits/reports/` that demonstrate coverage for the ingestion, semantic identities, directive contexts and non‑mutation rules. Update or create plan files as needed to document any discovered issues.
> **UI/tool surface:** Design and implement a minimal database‑backed workbench interface that reads from the new SQL core and displays datum rows and directive overlays in a spreadsheet‑like layout. Use a script‑driven tool interface and modularize it so it can evolve; start with read‑only display and sorting/filtering on `version_hash`/`hyphae_hash` and ensure the overlay is additive only, never mutating authoritative rows. Provide controls akin to a lightweight Google Sheets/Excel table. Include this tool in the codebase under `MyCiteV2/packages/tools/workbench_ui/` and add tests for rendering and non‑mutation behavior.
> **Documentation:** Audit and update all remaining documentation to reflect the completed SQL cut‑over and new UI. Ensure the final reports and plan files capture the new directive‑context overlay model and its non‑mutation validation gate. Summarize the final program in a closure report and mark `MOS‑C2` as completed.”

---


## FOLLUP REQUST UPDATE

> Help me follow up with my agent to help conclude this to an effective bench mark.

I’m grounding this in the current repo first so the cut-over plan matches the actual seams, data sources, and UI/runtime shape we already have. I’m checking the MOS program docs, where the FND source copy lives, and what tool/workbench surfaces already exist before I lock the completion plan.
Explored 3 files, 1 search
I’ve confirmed the MOS docs already treat Track A/B/C as complete in their current bounded form, so the “finish the program” ask is a real widening pass: repo ingestion, legacy retirement, final audits, and a sturdier workbench surface. I’m mapping the actual implementation targets now so the plan doesn’t assume seams or UI packages that aren’t really there yet.
Explored 2 files, 2 lists
There isn’t an existing workbench_ui package yet, which is helpful to know now rather than halfway through implementation. The current SQL datum-store can bootstrap from filesystem snapshots, but a true repo-ingestion/cut-over pass will need to go beyond that helper and explicitly define what gets migrated, what gets retired, and what “database-backed UI” means in this codebase.
Explored 1 file, 1 search, 2 lists
I’m down at the seam level now. The runtime today is payload-driven rather than a separate frontend app, and the system workspace already has a table-oriented workbench model, so the cleanest “Sheets-like” direction looks more like a new script-backed surface package than a heavyweight UI stack. I want to confirm that against the repo’s own tool contract before I lock the recommendation.
Explored 3 files, 1 list
The current shell already has the right kind of surface split for a utilitarian workbench: control_panel, workbench, and inspector, with the system workspace carrying a layered table payload. That means the plan can stay modular and script-grounded instead of inventing a new app framework, but I still need to pin down the exact cut-over boundary around FND’s private/hosted assets and legacy filesystem docs before I make that decision complete.
Explored 2 files, 2 searches
A couple of important truths are clear now. The repo already has a script area for data/audit work, and the FND deployed copy is the operative filesystem authority today, but the master plan still treats some host-bound/private assets as intentionally out of scope. That’s the one place where your requested “remove all filesystem authority” cut-over could change the program materially, so I want to surface that choice explicitly instead of burying it in implementation assumptions.
Explored 1 file, 2 lists, ran 1 command
The repo’s own contracts are pushing in one direction pretty strongly: tools should stay shell-attached and script-backed, not become a parallel app stack. That gives us a solid design default for the new workbench UI. The bigger remaining unknown is the migration breadth: whether final cut-over must absorb only the existing datum-authority surfaces, or every FND private/hosted filesystem artifact too.
Explored 3 files, ran 1 command
I’ve narrowed the last real decisions down to two things that the repo can’t answer for us on its own: how aggressive “remove all filesystem authority” should be for FND’s private/hosted assets, and whether the new workbench UI should stay inside the existing shell payload model or break out into a richer standalone renderer. Both materially change the implementation path, so I’m asking those directly instead of guessing.
Asked 2 questions
That helps a lot. We can keep the program crisp: complete the SQL authority cut-over for datum, audit, portal-authority, directive overlays, and the workbench/tool surface now, while treating host-bound private assets as an explicit documented exception rather than forcing new unrelated ports into the finish line. I’m doing one last pass over the authority and documentation seams so the final plan is implementation-ready and not hand-wavy.
Explored 2 files, 1 search, ran 1 command
One subtle part I don’t want to fake is directive-context migration. The repo has a new shared overlay model, but it doesn’t look like it already has a canonical filesystem store for those overlays, so I’m checking whether there’s anything concrete to extract or whether the right completion behavior is “no shared overlays inferred without an explicit manifest.”
Explored 2 searches
Worked for 5m 29s
I’ve got the last missing behavioral rule now: there isn’t a real preexisting shared directive-overlay store in the repo, only tool-local CTS-GIS state and the new SQL model. So the completion plan should explicitly forbid “guessing” overlays from old tool files and require an explicit migration manifest for any imported directive events. That keeps the final pass honest and audit-able.

Explored 1 file, 1 search
Plan

```plan
* MOS Final Cut-Over Completion Plan

    * Summary

- Extend `docs/plans/master_plan_mos.md` with a final Track A completion pass after the current `Phase 5`:
  - `Phase 6`: FND repo ingestion and SQL-only activation
  - `Phase 7`: legacy filesystem authority retirement
  - `Phase 8`: minimal SQL-backed workbench UI hardening
- Treat the migration corpus as `deployed/fnd/data/**` plus the portal-authority fields already represented by the current contracts from `deployed/fnd/private/config.json`.
- Keep `docs/plans/master_plan_mos.md` authoritative and update `docs/plans/master_plan_mos.index.yaml` with new entries `MOS-A6`, `MOS-A7`, `MOS-A8`, and one final closure/audit entry.
- Keep `MOS-C2` completed. Track C stays non-blocking and additive; do not widen shared-engine directive canon in this pass.

    * Key Changes

      * 1. Cut-Over Completion and Ingestion

- Add `MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py` as the one official cut-over script with `--dry-run` and `--apply`.
- The script must inventory every file under `deployed/fnd/data` and classify it into exactly one bucket:
  - `authoritative_import`: `data/system/anthology.json` and `data/sandbox/*/sources/**/*.json`
  - `supporting_anchor_context`: `data/sandbox/*/tool*.json`, attached as anchor rows/metadata, not imported as standalone authoritative documents
  - `derived_materialization`: `data/system/sources/*.json`, `data/payloads/cache/*.json`, and `data/system/system_log.json`
  - `explicit_exception`: binary payloads, `deployed/fnd/private/**` content not already covered by existing contracts, `deployed/fnd/public/**`, vault/key references, and other host-bound assets
- The script must write through existing SQL ports/adapters instead of duplicating persistence logic:
  - `SqliteSystemDatumStoreAdapter.store_authoritative_catalog(...)`
  - `SqliteSystemDatumStoreAdapter.store_system_workbench(...)`
  - `SqliteSystemDatumStoreAdapter.store_publication_summary(...)`
  - SQL portal-authority storage for the current `PortalAuthoritySource` shape
  - SQL audit-log import for any existing audit source
- `version_hash` and `hyphae_hash` must be produced through the existing Track B semantics path, not recomputed ad hoc in the script.
- The script must emit both JSON and Markdown ingestion reports with imported counts, per-document semantic coverage, derived-materialization counts, skipped exceptions, and any failures.
- Add one explicit failure gate: no FND datum row is considered migrated unless it is either present in SQL semantics or listed in the exception manifest with a reason.

      * 2. Directive Context and Non-Inference Rule

- Do not infer shared directive overlays from CTS-GIS tool-local runtime state, old notes, or arbitrary tool files.
- If directive overlays must be preserved, require a dedicated migration manifest with normalized snapshot/event records keyed by `version_hash` and optional `hyphae_hash`.
- If no manifest is supplied, the cut-over must write zero shared directive events and produce a report stating that no canonical shared overlays existed to import.
- Keep directive context additive only:
  - runtime may read overlays
  - runtime may summarize overlays
  - runtime may never mutate authoritative datum rows through directive state

      * 3. SQL-Only Runtime and Legacy Retirement

- After a successful apply migration, switch shared runtime composition to SQL-only for migrated surfaces.
- Remove public runtime support for `authority_mode=filesystem` and `authority_mode=shadow` from shared shell/system workspace entrypoints; missing or uninitialized DB should become an explicit startup/readiness failure, not a silent bootstrap.
- Remove shared-runtime dependence on `FilesystemSystemDatumStoreAdapter` and `FilesystemAuditLogAdapter`.
- If filesystem parsing logic is still needed for migration tests, move it into migration-script-local helpers or fixture readers rather than keeping general-purpose filesystem authority adapters in active runtime code.
- Retire legacy filesystem authority docs and tests once SQL-only replacements exist; keep only migration-fixture coverage where it proves ingestion correctness.
- Keep host-bound private assets as explicit retained exceptions in the master plan until dedicated ports exist; do not claim they are SQL-owned in this pass.

      * 4. Minimal Database-Backed Workbench UI

- Add `MyCiteV2/packages/tools/workbench_ui/` as a shell-attached, script-backed tool package, not a separate frontend stack.
- Introduce one new SYSTEM child tool surface for the utilitarian SQL workbench:
  - tool id: `workbench_ui`
  - public route: `/portal/system/tools/workbench-ui`
- The tool package should own:
  - a SQL-backed read service using `SystemDatumStorePort` and `DirectiveContextPort`
  - a normalized table payload builder
  - control-panel payloads for filtering/sorting
  - interface-panel payloads for selected-row detail and additive overlay summary
- The first pass must stay read-only and spreadsheet-like:
  - primary table columns: `datum_address`, `layer`, `value_group`, `iteration`, `labels`, `relation`, `object_ref`, `hyphae_hash`
  - document-level header state: `document_id`, `version_hash`, row count, warnings
  - controls: document picker, text filter, sort key, sort direction, overlay visibility toggle
  - interface panel: selected row raw payload, semantic identity, directive overlay summary, no mutation controls
- Reuse the existing shell region model: `Control Panel`, `Workbench`, and `Interface Panel`.
- Also simplify the existing SYSTEM root workbench payload by reusing this table/presenter logic where practical, but do not turn the tool package into a second shell.

      * 5. Final Audits and Documentation Closure

- Add final reports under `docs/audits/reports/` for:
  - FND SQL ingestion coverage
  - SQL-only authority activation and legacy retirement
  - directive-context non-mutation / non-inference validation
  - documentation alignment and historical cleanup
  - overall MOS program closure
- Update active docs so they consistently describe SQL-backed authority for migrated FND/System surfaces:
  - `docs/plans/master_plan_mos.md`
  - `docs/plans/master_plan_mos.index.yaml`
  - `docs/plans/README.md`
  - `docs/audits/README.md`
  - `docs/plans/documentation_ia_remediation_backlog.md`
  - `docs/contracts/portal_shell_contract.md`
  - `docs/contracts/route_model.md`
  - `docs/contracts/surface_catalog.md`
  - `MyCiteV2/instances/_shared/runtime/README.md`
- Historical intermediate cut-over docs should be retained only as historical evidence and clearly marked as superseded by the closure artifacts.
- The closure report must explicitly state:
  - what is now SQL-authoritative
  - what legacy code/docs were removed
  - what remains as documented non-blocking exception scope
  - that `MOS-C2` remains completed and additive-only

    * Public Interfaces and Contract Changes

- Shared runtime entrypoints stop advertising filesystem/shadow authority modes for migrated surfaces.
- New migration CLI:
  - `python3 MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py --data-root deployed/fnd/data --portal-config deployed/fnd/private/config.json --authority-db <path> --tenant-id fnd --tenant-domain fruitfulnetworkdevelopment.com --dry-run|--apply --report-json <path> --report-markdown <path>`
- New tool surface:
  - route `/portal/system/tools/workbench-ui`
  - SQL-backed, read-only, table-first workbench model
- New directive migration rule:
  - shared directive snapshots/events may only come from an explicit migration manifest, never heuristic extraction

    * Test Plan

- Dry-run migration proves every file in `deployed/fnd/data` is imported, derived-only, or exception-listed.
- Apply migration to a temp DB and verify authoritative catalog, document semantics, row semantics, portal authority, audit history, and directive-event counts.
- Run one final parity comparison between pre-cutover filesystem outputs and post-cutover SQL outputs for the SYSTEM workbench and approved authority surfaces.
- Add SQL-only runtime tests proving no filesystem adapter path is exercised for migrated FND surfaces.
- Add `workbench_ui` tests for route composition, table payload shape, sort/filter behavior, `version_hash`/`hyphae_hash` display, and additive overlay rendering.
- Add non-mutation tests proving UI/tool reads never rewrite authoritative datum rows and directive context stays overlay-only.
- Validate the updated YAML index and add grep/link checks so active docs no longer describe filesystem authority for migrated surfaces.

    * Assumptions and Defaults

- Scope is `datum-first`: migrate `deployed/fnd/data/**` and current portal-authority fields already covered by active contracts; keep other private/host-bound assets as explicit exceptions for later porting.
- No shared directive overlays are imported unless an explicit migration manifest is supplied.
- `workbench_ui` ships as a shell-attached tool surface, not a standalone UI framework.
- SQLite remains the repo execution target for the cut-over pass, while ports and schema language stay vendor-neutral.
```

I’m starting by checking the current repo state and the existing shell/runtime seams so I can land this as a clean completion pass rather than layering over stale assumptions. Then I’ll wire the migration script, SQL-only runtime path, and the new workbench tool surface together with docs and audits in one pass.
Explored 2 files, 1 list, ran 1 command
I’ve confirmed the worktree is clean, which is great for a pass this size. I’m mapping the remaining runtime authority dependencies now so we can cut over cleanly instead of leaving hidden filesystem reads behind in the shared shell.
Explored 6 files, 5 searches
I’ve reached the main implementation fork: the shared shell still has a few hard-wired filesystem authority paths, especially around the SYSTEM runtime. I’m measuring how wide that dependency is before I cut it over, so we can replace the live path without destabilizing unrelated tooling that isn’t part of the datum-first scope.
Explored 4 files, 3 searches
I’ve locked the practical cut-over shape now: SYSTEM/runtime authority will go SQL-only, the migration script will own any remaining filesystem parsing, and the new workbench surface will sit on top of that SQL core instead of inventing another UI stack. I’m editing the shared seams first so the migration and tool work land on the final authority model, not the old dual-mode one.
Explored 9 files, 10 searches, 1 list
Context automatically compacted
I’m moving from the program docs into the actual cut-over mechanics now: first I’m wiring the SQL-only runtime path and the new workbench_ui surface, then I’ll add the FND ingestion script and close the loop with tests and final audit docs.
Explored 4 files
I’ve confirmed the main loose end: the shared runtime still silently bootstraps and falls back to filesystem authority. I’m patching that out now while adding the spreadsheet-style workbench_ui tool so the cut-over becomes explicit instead of half-switched.
Explored 6 files, 3 searches
I’ve got the shell contract constraints in view too: the old registry still hard-codes every tool as interface-panel-only, so I’m relaxing that just enough for a utilitarian workbench tool without turning the shell into a second app.
Explored 14 files, 4 searches, 2 lists
The runtime side is broader than just one adapter swap: host config, shell catalog, and contract tests all assume the old mixed mode. I’m aligning those together so we don’t end up with a “SQL-only” plan but a filesystem-first actual host.
Explored 11 files, 7 searches
I’ve got enough context to start the actual patch set. The implementation is breaking into four linked slices so we can keep momentum and still verify each piece:

SQL-only activation: remove filesystem/shadow behavior from the shared runtime and host, require an authority DB for migrated SYSTEM surfaces, and wire new readiness errors.
Workbench tool: add workbench_ui as a shell-attached, workbench-primary SYSTEM tool with SQL-backed table payloads and additive directive-overlay summaries.
FND ingestion: add the one official migration CLI, inventory/classification reporting, SQL writes through existing adapters, and zero-inference directive import behavior unless a manifest is supplied.
Closure pass: update tests, run targeted regression/migration checks, then synchronize master_plan_mos.md, the YAML index, and final audit/closure artifacts with concrete evidence.
I’m in the contract layer now. This patch is the hinge for the UI work: it adds the new tool surface and lets one tool be workbench-primary without disturbing the existing interface-panel-first tools.
Edited 1 file
The shell contract is open enough now for a workbench-primary tool. I’m wiring the runtime catalog and host routes next so the new surface is actually reachable and the SQL-only requirement becomes part of the public entrypoints.
Edited 3 files, explored 2 files, 2 searches
The runtime patch is the critical cut-over step. I’m removing the silent seeding/bootstrap path now, then I’ll layer the migration CLI on top of that instead of letting production requests keep doing hidden filesystem imports.
Edited 1 file, explored 5 files, 3 searches
I’m on the new workbench surface now. The aim for this first pass is intentionally plain: a sturdy SQL-backed grid with sort/filter/query controls and additive overlay inspection, not another custom frontend stack.
Created 3 files
The workbench_ui runtime is coming together as a regular shell-attached tool, not a side app. That keeps the cut-over cleaner: one shell, SQL authority underneath, and a table-first read surface on top.
Created 1 file
I’m switching into ingestion now. Before I wire the CLI, I’m checking the actual FND corpus shape so the script’s classification rules match the repo instead of an imagined layout.
Explored 2 lists, ran 1 command
The migration script is the cut-over executor, so I’m giving it two jobs at once: real SQL writes through the existing adapters, and enough reporting to prove every FND file ended up either imported, derived, or explicitly retained.
Created 1 file
I’ve finished the first big code pass. I’m doing a compile sweep now before I touch tests so we can separate plain syntax/import issues from behavioral regressions.
Edited 1 file, explored 1 file, 1 search, ran 3 commands
I’m into the regression layer now. A few existing tests were asserting the old world on purpose, so I’m updating them to make the new cut-over rules explicit instead of letting them fail ambiguously.
Created 3 files, edited 4 files, deleted 1 file, explored 3 files, 3 searches, ran 2 commands
The new unit coverage is green. I’m pushing outward into the shared runtime and host integration tests now, because those are the places where “SQL-only” tends to leave hidden fallbacks behind.
Ran 2 commands
The host integration file is skipped in this environment, which is fine. The broader workspace runtime suite is still running, and that’s the one most likely to catch any accidental filesystem assumptions.
Edited 1 file, explored 1 file, 1 search, ran 1 command
The runtime and tool-side regressions are stable now. I’m moving into the real FND ingestion pass next so the final docs can point at actual migration evidence instead of just tests.
Explored 1 list, ran 1 command
The migration CLI itself is fine, but running it from the repo root exposed one packaging loose end: it needs to bootstrap the repo path the same way the test modules do. I’m fixing that now, then I’ll run the dry-run/apply against the real FND copy.
Edited 1 file, explored 1 file, ran 3 commands
The dry-run surfaced one real loose end instead of an implementation bug: the FND copy has the public profile files, but the anthology doesn’t currently resolve fruitfulnetworkdevelopment.com through the publication-summary mapping. I’m checking the actual public docs now so we can close that gap deliberately instead of papering over it.
Explored 3 files, 1 search, ran 1 command
I found the gap: the FND public profile pair exists, but the anthology doesn’t currently carry the domain row the old filesystem summary reader expects. I’m adding a migration-only fallback that promotes the existing public/tenant profile pair into SQL with an explicit provenance note, so the cut-over can close without pretending that row already exists.
Edited 1 file, ran 3 commands
The dry-run closes cleanly now, including the publication summary via the explicit public-profile fallback. I’m applying the migration into the real FND SQL authority file next and then I’ll use that concrete evidence to finish the closure docs.
Explored 1 file, ran 4 commands
The real migration completed cleanly: 409 authoritative documents, 3,133 semantic rows, SQL portal authority present, and zero shared directive imports because no manifest was supplied. I’m doing one runtime smoke pass against the freshly built FND authority file, then I’ll lock the docs and closure reports to those concrete numbers.
Ran 2 commands
I’ve got the actual cut-over evidence now, so I’m locking the documentation to the real state instead of a planned one: new phases, final statuses, superseded intermediate artifacts, and the explicit non-inference / non-mutation gate.
Explored 4 files
Context automatically compacted
I’m carrying the cut-over through the remaining closure work now: syncing the master plan/YAML, writing the final audit artifacts, and tightening the docs so the repo clearly reflects SQL-only authority for the migrated FND surfaces.
Explored 3 files, ran 1 command
I’ve got the runtime and migration path in place; the next step is making the repo tell the same story everywhere, including the final audits and the contract docs that still describe the older authority posture.
Explored 7 files, 1 search
I’m pulling the plan and contract tails now so I can patch them cleanly rather than bolting on contradictory status text. After that I’ll write the closure artifacts and run the doc-alignment and runtime regressions again.
Explored 8 files, 2 lists
The repo already has the hard cut-over mechanics; what’s left is making the docs, audits, and closure criteria explicit enough that a reviewer can verify the migration without having to reverse-engineer it from the code.
Explored 2 files, 1 search
I’m at the point where the main engineering choice is how explicit to make the retirement story. I’m taking the stricter path: public runtime goes SQL-only for migrated SYSTEM surfaces, while the filesystem adapter code is documented as migration/test-only evidence instead of pretending it is still an active authority path.
Explored 5 files, 1 list, ran 1 command
I’m tightening one last area before the doc pass: whether the migrated authority DB should live as source or artifact. I’m treating it as generated runtime state, not canonical source, so the docs will point to the migration command and audit reports rather than turn the sqlite file into repo truth.

Explored 1 search
Ran if [ -f /srv/repo/mycite-core/.gitignore ]; then sed -n '1,240p' /srv/repo/mycite-core/.gitignore; fi
Exploring
Searched for sqlite\|authority.sqlite\|mos_authority in .gitignore
0 out of 5 tasks completed
17 files changed
+1692
-212

Review
changes

---


## FOLLOW UP PROMPT

Follow‑up for concluding MOS cut‑over tasks

Use the following precision prompt when following up with your agent to complete the remaining tasks:

> **Prompt for the agent:**
>
> **Finalize Phase 6–8:** Update `master_plan_mos.md` to add `Phase 6` (FND ingestion and SQL-only activation), `Phase 7` (retirement of legacy filesystem authority), and `Phase 8` (minimal SQL‑backed workbench UI hardening). Create corresponding `MOS-A6`, `MOS-A7`, and `MOS-A8` entries in `master_plan_mos.index.yaml`.
> **Migration script:** Implement `migrate_fnd_repo_to_mos_sql.py` to inventory every file under `deployed/fnd/data/**` and classify each as authoritative import, supporting anchor context, derived materialization, or explicit exception. Use existing SQL adapters (`SqliteSystemDatumStoreAdapter`, `SqliteAuditLogAdapter`, `SqlitePortalAuthorityAdapter`, etc.) to persist data. Produce both JSON and Markdown ingestion reports listing imported rows, semantic coverage, skipped items, and failures. Do not recompute `version_hash` or `hyphae_hash`; use the existing Track B semantics.
> **Directive context:** Do not infer directive overlays from old CTS‑GIS tool files. Only import directive overlays when an explicit manifest is provided; otherwise write zero shared overlays. Ensure the runtime enforces the read‑only, non‑mutation rules.
> **SQL‑only runtime:** Remove the `filesystem` and `shadow` authority modes from the shared runtime. After migration, the system should run solely on the SQL authority for migrated surfaces. Move any leftover filesystem parsing code into test/migration helpers, and retire the filesystem authority adapters.
> **Workbench UI:** Add a new workbench UI tool under `MyCiteV2/packages/tools/workbench_ui/` and expose it via `/portal/system/tools/workbench-ui`. This tool should present a spreadsheet‑like table of datum rows (layer, value group, iteration, labels, relation, object_ref, hyphae_hash) and document header metadata. Implement sorting and filtering controls. Summarize directive context overlays separately and never mutate authoritative rows.
> **Documentation and audits:** After completing migration and UI work, update all relevant docs and plans (including the final closure artifact and audit reports) to reflect the SQL‑only cut‑over. Add a final audit entry verifying that every FND datum row is either imported into SQL semantics or explicitly listed as an exception. Update tests accordingly.

Ensure all tasks are fully implemented, documented, and tested before claiming the program complete.

---


## INPUT 6

Consider out put and updated repo and how I proceed with my plan:
The resulting pass needs to completion of loose ends and amking sure to externalize the plans and audits to be completed for further comprehensive review of all data from the fnd portal repo copy to ensure its thoroughly combed over for alignment to the new paradigm.
This should proceed ingesting the data in the new MOS backed database with the newly defined convention.
This should allow for a complete switch over to the new portal paradigm and the removal of legacy code, documentation ect. Thus completing the cut over. Instruct the agent to additional comprehensively audit the documentation to ensure the everything is robustly represented.

Lastly review the visualization so that the result is a more clear datum file workbench by enabling the use of a data base using and backed UI/tool interface surface for the use of a script based tool interface surface.
It should be clear cut and utilitarian, akin to google sheets/excel type programs. Starting minimal is best. Hardening and simplification for a utilitarian reflective content and controls for the control panel.
Make sure the tool interface surface is sturdy and investigated for good design modularization and reflective of what is meant to be a materialization of a script grounded interface surface.
The lynch pin of this part of the consolidation simplification is having a better tool interfaces by making sure the the visualization of the state and output for mediation (with respect to sources) can be made less heavy and less developmentally intensive by have it now backed by the data base usage and a script based tool interface surface.

To finish the MOS program, use this precision prompt to instruct your Codex agent:

**Complete the MOS cut‑over by ingesting the FND portal repository into the SQL‑backed datum store and replacing all filesystem authority.**
**Ingestion:** Write a migration script to traverse the FND portal repo copy, compute `version_hash` and `hyphae_hash` for each datum document, insert the rows into the MOS database via `datum_store` and `datum_semantics`, and record any `directive_context_events` needed to preserve tool‑local overlays. Verify no legacy rows remain unaccounted for.
**Legacy removal:** Remove the old filesystem‑backed adapters, data, and documentation once ingestion is complete and update `master_plan_mos.md` and `master_plan_mos.index.yaml` to mark the cut‑over and document removals.
**Comprehensive audits:** Draft and execute final audits to confirm that all data from the FND copy align with the new MOS conventions. Generate audit reports under `docs/audits/reports/` that demonstrate coverage for the ingestion, semantic identities, directive contexts and non‑mutation rules. Update or create plan files as needed to document any discovered issues.
**UI/tool surface:** Design and implement a minimal database‑backed workbench interface that reads from the new SQL core and displays datum rows and directive overlays in a spreadsheet‑like layout. Use a script‑driven tool interface and modularize it so it can evolve; start with read‑only display and sorting/filtering on `version_hash`/`hyphae_hash` and ensure the overlay is additive only, never mutating authoritative rows. Provide controls akin to a lightweight Google Sheets/Excel table. Include this tool in the codebase under `MyCiteV2/packages/tools/workbench_ui/` and add tests for rendering and non‑mutation behavior.
**Documentation:** Audit and update all remaining documentation to reflect the completed SQL cut‑over and new UI. Ensure the final reports and plan files capture the new directive‑context overlay model and its non‑mutation validation gate. Summarize the final program in a closure report and mark `MOS‑C2` as completed.||

OUTPUT:
Phase 6–8 are now implemented and closed in the repo. [master_plan_mos.md](/srv/repo/mycite-core/docs/plans/master_plan_mos.md) and [master_plan_mos.index.yaml](/srv/repo/mycite-core/docs/plans/master_plan_mos.index.yaml) now mark `MOS-A6`, `MOS-A7`, `MOS-A8`, and program closure complete. The migration CLI is in [migrate_fnd_repo_to_mos_sql.py](/srv/repo/mycite-core/MyCiteV2/scripts/migrate_fnd_repo_to_mos_sql.py), and I ran it against the FND copy to produce the new ingestion reports in [mos_fnd_sql_ingestion_coverage_report_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_fnd_sql_ingestion_coverage_report_2026-04-21.md) and its JSON companion. The executed coverage pass records `409` authoritative documents, `3133` authoritative datum rows, `25215` supporting anchor rows, and `0` shared directive snapshots/events because no explicit directive manifest was supplied.

The shared runtime is now SQL-only for migrated `SYSTEM` surfaces through [app.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/app.py), [portal_shell_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py), and [portal_system_workspace_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/portal_system_workspace_runtime.py). The new read-only spreadsheet-style tool lives under [MyCiteV2/packages/tools/workbench_ui/](/srv/repo/mycite-core/MyCiteV2/packages/tools/workbench_ui) and is exposed by [portal_workbench_ui_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py) at `/portal/system/tools/workbench-ui`. Contract docs and closure audits are updated, including [portal_shell_contract.md](/srv/repo/mycite-core/docs/contracts/portal_shell_contract.md), [route_model.md](/srv/repo/mycite-core/docs/contracts/route_model.md), [surface_catalog.md](/srv/repo/mycite-core/docs/contracts/surface_catalog.md), [mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md), [mos_directive_context_non_inference_validation_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_directive_context_non_inference_validation_2026-04-21.md), [mos_documentation_alignment_and_cleanup_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_documentation_alignment_and_cleanup_2026-04-21.md), and [mos_program_closure_report_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_program_closure_report_2026-04-21.md).

Verification passed with `py_compile`, YAML parsing of the MOS index, `85` targeted tests green, and the host integration suite reporting `5` skipped in this environment.

---


## OUTPUT 6 ~ Final MOS closure tasks

> **Prompt for the agent:**
>
> The MOS program is now at Phase 6–8 completion. All FND data has been ingested and the SQL‑only runtime and spreadsheet‑like workbench UI are live. Proceed with final closure by:
>
> 1. **Legacy cleanup:** Verify that no legacy filesystem adapters, data or docs remain. Remove any residual files and references. Update `master_plan_mos.md` and `master_plan_mos.index.yaml` to note the removal and confirm cut‑over completion.
> 2. **Comprehensive audits:** Review every documentation file and plan in `docs/plans/` and `docs/audits/reports/` to ensure they accurately reflect the SQL‑only paradigm. Produce an audit checklist and reports under `docs/audits/reports/` confirming that all FND documents (409 imported documents, 3133 rows, 25215 anchors) were ingested and that there are no untracked rows or missing directives.
> 3. **UI/tool review:** Evaluate the new workbench UI for clarity and utility. Ensure the interface behaves like a lightweight spreadsheet: read‑only, sortable/filterable by `version_hash` and `hyphae_hash`, additive overlays only, and modularized so it can be extended. Document any usability issues or design improvements and update `portal_workbench_ui_runtime.py` accordingly.
> 4. **Closure report:** Draft a final closure report summarizing ingestion results, audits, legacy removal, and UI evaluation. Place this in `docs/audits/reports/mos_program_closure_report_2026-04-21.md` or similar. Mark `MOS‑C2` and the program as fully complete in the YAML index.


---

## Completion OUTPUT

Implemented the MOS closure pass end to end.

**What Changed**

* The workbench now behaves as the intended two-pane, read-only SQL spreadsheet in [service.py](/srv/repo/mycite-core/MyCiteV2/packages/tools/workbench_ui/service.py:279) and [portal_workbench_ui_runtime.py](/srv/repo/mycite-core/MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py:90): document-table controls use `document_filter` / `document_sort` / `document_dir`, row-grid controls keep backward-compatible `filter` / `sort` / `dir`, `version_hash` and `hyphae_hash` are first-class, and overlays stay additive-only.
* The public route/query contract was updated to match that surface in [route_model.md](/srv/repo/mycite-core/docs/contracts/route_model.md:106), and the plan/index now record SQL-only cutover completion plus completed `MOS-C2` and program closure in [master_plan_mos.md](/srv/repo/mycite-core/docs/plans/master_plan_mos.md:41) and [master_plan_mos.index.yaml](/srv/repo/mycite-core/docs/plans/master_plan_mos.index.yaml:214).
* I added the closure audit corpus and closure-specific verification in [mos_program_closure_audit_checklist_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_program_closure_audit_checklist_2026-04-21.md:1), [mos_program_closure_report_2026-04-21.md](/srv/repo/mycite-core/docs/audits/reports/mos_program_closure_report_2026-04-21.md:1), and [test_mos_program_closure.py](/srv/repo/mycite-core/MyCiteV2/tests/unit/test_mos_program_closure.py:17).
* The refreshed reports now explicitly state `409` authoritative documents, `3133` authoritative rows, `25215` anchor rows, `0` directive snapshots, `0` directive events, `0` untracked authoritative rows, and no missing directive imports because no manifest was supplied.
* Per the agreed authority-only cleanup assumption, I did not delete `deployed/fnd/data/**` or fixture/bootstrap assets; instead, active MOS/FND filesystem and `shadow` authority posture was retired and retained assets are now labeled non-authoritative historical/test support.

**Verification**

* Passed: `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`
* Passed: `python3 -m unittest MyCiteV2.tests.unit.test_migrate_fnd_repo_to_mos_sql`
* Passed: `python3 -m unittest MyCiteV2.tests.unit.test_portal_shell_sql_authority`
* Passed: `python3 -m unittest MyCiteV2.tests.unit.test_portal_workspace_runtime_behavior`
* Passed: `python3 -m unittest MyCiteV2.tests.unit.test_mos_program_closure`
* Passed: `python3 -m unittest MyCiteV2.tests.adapters.test_sql_datum_store_adapter`
* Passed: `python3 -m unittest MyCiteV2.tests.adapters.test_sql_directive_context_adapter`
* Passed: `python3 -m unittest MyCiteV2.tests.unit.test_portal_system_workspace_directive_context`
* Passed: `python3 -m unittest MyCiteV2.tests.contracts.test_contract_docs_alignment`

No blocking issues remained after the pass.
