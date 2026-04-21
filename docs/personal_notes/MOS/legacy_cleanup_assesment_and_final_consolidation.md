# Legacy cleanup assessment and final consolidation prompt

Yes. At this point the MOS cut-over and the post-closure consolidation pass are both complete. The repo state you quoted means the program is no longer in “finish the cut-over” mode. It is now in “follow-on hardening and focused evolution” mode.

The main MOS concerns from the personal notes have been touched in the right way. The SQL-backed core direction, file-shaped authority surface, portal-instance authority model, bounded cut-over, and adapter-swap architecture were canonized from the SQL core declaration draft . The originally unclear areas from the investigation note—MSS hashing, hyphae derivation, deterministic edit/remap, and directive-context scope—were the exact gaps later turned into explicit semantic gates and bounded directive handling, so that note is functionally superseded rather than still open-ended . The schema note’s core ideas—ordered datum rows, structural coordinates, relational persistence, raw-versus-projected access, and database-backed handling of datum content—were largely carried into canon, but its more speculative table decompositions and generalized lens ideas remain source material rather than final canon . The broader database-use note also mixed durable direction with speculative implementation ideas, so “partially canonized” is the right result there . The novelty note still reads like positioning source material rather than fully proven canon, so “partially canonized” is also the right result there . The cut-over consideration note was planning fuel and is now correctly superseded by the canonical plan and closure artifacts .

The visualization point is now clear enough to narrow. The correct forward term is not “page” or “viewer.” It is the **datum-file workbench**. V1 evidence supports that language specifically: anchor file, layered datum table, datum row, inline datum editor, workbench lens, and structural coordinates are the right conceptual terms for the surface you are trying to harden . Since the current repo already moved to a read-only two-pane SQL-backed spreadsheet, the next work should be hardening that datum-file workbench, not re-litigating whether a database-backed script surface is the right direction. That direction is already established.

This focuses on consolidating documentation and hardening the datum‑file workbench. Be explicit to instruct the removal of every residual filesystem reference or personal note. The crosswalk and closure audits show that old authority modes are already retired for the system surfaces and that host‑bound assets remain documented exceptions. The personal notes are now classified as source evidence, partially canonized, superseded or deferred; they are not removed but are no longer active planning files. If your goal is to physically eliminate all legacy code and documentation rather than simply classify them, you would need an additional clean‑up pass.

This prompt ensures you search for and remove obsolete legacy code, archive superseded notes, sweep documentation for stale references, clarify the scope of retained file assets, and complete the UI hardening—all while preserving the integrity of the completed MOS program.


> **Do not reopen the MOS cut‑over or alter the new SQL‑only authority. Treat all completed closure and crosswalk documents as authoritative.**
>
> **Objective:** perform a one‑time legacy cleanup pass to remove or archive residual filesystem/shadow code outside the documented exception scope, eliminate stale personal notes if they are no longer needed, and ensure the new paradigm is the only active operational mode.
> * Execute the next minimal hardening pass for the SQL-backed datum-file workbench and tighten its documentation/spec so the surface is clearly the canonical script-grounded workbench for datum inspection.

> **Tasks:**
>
> 1. **Residual code search:** Search the entire repository for references to `Filesystem` or `authority_mode` values other than `sql_primary`. For each occurrence, classify whether it is:
>      • a required host‑bound exception (CTS/GIS, FND DCM/EBI, network read‑model) as documented in the closure plan; or
>      • obsolete MOS code relating to retired “filesystem” or “shadow” authority. Remove or refactor the obsolete code so that only the documented exception surfaces depend on files.
> 2. **Personal notes disposition:** Based on the crosswalk, archive or delete any personal notes marked `superseded` or `source‑only` if you no longer need them. Update `docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md` to reflect which files were removed or archived.
> *  Harden `workbench_ui` only. Do not widen shared-engine NIMM/AITAS canon. Do not reopen migration or SQL-only authority work.
> * Treat the surface as the canonical **datum-file workbench** for the SYSTEM anchor file and related authoritative documents.
> * Keep it shell-attached, script-backed, read-only, additive-only, and utilitarian.
> 3. **Documentation sweep:** Re‑scan all markdown and YAML files to ensure no stale references remain to the retired master‑plan basename, `filesystem` authority, or pending MOS cut‑over work. Update or remove wording as needed so that all docs reflect the completed SQL‑only paradigm.
> * Create or update one focused spec/audit pair that records the implemented hardening pass.
> * Ensure the terminology is consistent:
>
>   * datum-file workbench
>   * anchor file
>   * layered datum table
>   * datum row
>   * workbench lens
>   * structural coordinates
> * Remove any wording that still makes the surface sound provisional if the implementation is now stable.
> 4. **Review:**`docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md` and `docs/audits/reports/workbench_ui_utilitarian_design_audit_2026-04-21.md` and turn the highest-value findings into concrete implementation tasks.
> * Improve the current two-pane workbench so it more clearly behaves like a lightweight spreadsheet/workbench:
>   * stronger document selection state
>   * clearer row selection state
>   * frozen or visually stable headers where appropriate
>   * keyboard-friendly navigation if it can be done without adding framework weight
>   * optional grouping or filtering by structural coordinates (`layer`, `value_group`, `iteration`)
>   * explicit `version_hash` and `hyphae_hash` affordances as first-class workbench identities
>   * raw-versus-interpreted presentation toggle only if it remains simple and script-grounded
>   * clearer source/overlay visibility controls while preserving additive-only behavior
> * Keep the control panel sparse and sturdy. Prefer a small number of durable controls over rich UI complexity.
> * Preserve the contract language that this is a **datum-file workbench**, not a separate app and not a generalized spreadsheet editor.
> 5. **Exception scope clarity:** For host‑bound directories like `deployed/fnd/data/**`, add a brief explanatory note in `docs/plans/mos_post_closure_consolidation_plan_2026-04-21.md` clarifying that these assets are retained as non‑authoritative historical/test support and are outside MOS authority.
> 6. **Workbench hardening follow‑on:** Proceed with the previously defined workbench UI hardening tasks, but ensure any UI changes remain compatible with the cleaned codebase.
> 7. **Verification:** After the cleanup, run the full test suite and update the closure audit checklist to record that all obsolete code and documentation have been removed or archived. Cite which files were deleted and which remain as historical evidence.
> * Add or update targeted tests for the hardening pass.
> * Re-run `test_workbench_ui_runtime`, `test_contract_docs_alignment`, and any new workbench-ui tests added in this pass.
> * Report only concrete residual deficiencies that remain after the hardening pass.