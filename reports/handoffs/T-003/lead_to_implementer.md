# Lead → Implementer: T-003 shell region and kind contracts

## Task classification

- **primary_type:** `repo_only` (confirmed; no live systems in scope).
- **Evidence for closure:** Contract document at `MyCiteV2/docs/contracts/shell_region_kinds.md` (or task-approved equivalent path), implementation report, implementer→verifier handoff, independent verifier pass. No deploy or live URL checks required.

## Exact files to read (in order)

1. `MyCiteV2/docs/ontology/structural_invariants.md` — navigation purity, shell vs tool boundaries.
2. `MyCiteV2/docs/plans/authority_stack.md` and `MyCiteV2/docs/ontology/interface_surfaces.md` — task authority list.
3. `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` — region schemas, `build_shell_composition_payload`, `build_portal_activity_dispatch_bodies`, `foreground_region_for_surface`, `inspector_collapsed_for_surface`, workbench/inspector payload builders and any `kind` / surface discriminant.
4. `MyCiteV2/instances/_shared/runtime/admin_runtime.py` — functions that emit or assemble `shell_composition` and region payloads into the runtime envelope.
5. `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js` — `applyChrome`, region render branches (workbench, inspector, activity bar, control panel), handling of `composition_mode` and `foreground_shell_region`.
6. `MyCiteV2/docs/contracts/README.md` — align tone and cross-links with existing contract docs.

## Exact goal

Produce a **single canonical contract document** that makes implicit shell region conventions explicit: enumerate every supported **workbench** and **inspector** kind (and any other region kinds if the code uses a unified discriminant), document required vs optional fields per kind, map each kind to the **runtime function(s)** that emit it and the **client renderer branch** that consumes it, and clearly separate **shell composition contract** (serializable truth from runtime) from **presentation behavior** (DOM/CSS/UX in JS).

The task file names the deliverable as `MyCiteV2/docs/contracts/shell_region_kinds.md` (`artifacts.contract_doc`); use that path unless you discover a naming conflict with `docs/contracts/README.md`, in which case note it in the implementation report and align with the task owner.

## Constraints that matter

- Derive the contract **from the three scoped code files**, not from chat or archive narrative (`agent/constraints.md` §2–3, §7).
- Cite the task **authority** paths inside the new doc.
- Preserve invariants: **shell_composition** is shell truth; tools attach through shell-defined surfaces; **UI widget is not a shell surface**; do not document alternate “browser shell” state.
- Keep extension notes for future tools **short and actionable** per task YAML.

## Required outputs

1. **Contract doc:** `MyCiteV2/docs/contracts/shell_region_kinds.md` (per task `artifacts.contract_doc`), satisfying every bullet under task `acceptance:` (enumeration of workbench kinds, inspector kinds, fields, runtime emitters, client consumers, composition_mode / foreground region semantics, contract vs presentation).
2. **Implementation report:** `reports/T-003-implementation.md` with the sections required by `tasks/README.md` §9 (files changed, why, commands, tests, deploy N/A, gaps, recommended next status).
3. **Handoff:** `reports/handoffs/T-003/implementer_to_verifier.md` per `tasks/README.md` §8.
4. **Task YAML updates (implementer):** After work, set `status` to `verification_pending` (or `blocked` if stuck), `execution.current_role` to `verifier`, `execution.next_role` to `lead`. Do **not** set `verification_result` or mark the task resolved.

## Stop conditions

- Stop and set task `blocked` with reason in the implementation report if the code and an honest contract cannot be reconciled (e.g. ambiguous kinds with no single emitter).
- Do not invent kinds or fields not present in the scoped Python/JS; if something looks like a kind in HTML only, classify it as presentation, not contract.
- `repo_test_command` is `not_applicable`; run targeted checks only if you add code (you should not need to for a doc-only task).

## Recommended next task status after implementation

- `status: verification_pending`
- `execution.current_role: verifier`
- `execution.next_role: lead`
- Leave `verification_result: pending` for the verifier.
