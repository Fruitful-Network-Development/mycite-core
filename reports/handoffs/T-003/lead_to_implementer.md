# Lead → Implementer handoff: T-003

## Task classification

- **Primary type:** `repo_only` (documentation derived from repo code; no deploy or live URL acceptance).
- **Evidence for closure:** Implementation report, contract document at scoped path, implementer→verifier handoff; verifier must independently diff doc vs. the three code files listed in the task.
- **Verifier:** Required (`requires_verifier: true`). Lead does not close until `verification_result: pass` and verifier handoff recommend resolution.

## Exact files to read (minimal)

1. `agent/constraints.md` — authority order, shell invariants, minimal-context rule.
2. `tasks/T-003-shell-region-contracts.yaml` — objective, acceptance, artifacts, closure rule.
3. **Scope — derive contract only from these implementations:**
   - `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py`
   - `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
   - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js`
4. **Authority citations for the doc (open as needed for quotes / invariants):**
   - `MyCiteV2/docs/ontology/structural_invariants.md`
   - `MyCiteV2/docs/plans/authority_stack.md`
   - `MyCiteV2/docs/ontology/interface_surfaces.md`
5. **Output location:** `MyCiteV2/docs/contracts/` (create `shell_region_kinds.md` if missing).

Do not expand scope beyond these paths unless a contradiction in the three primary code files forces a one-hop read elsewhere—and then record that in the implementation report.

## Exact goal

Produce **`MyCiteV2/docs/contracts/shell_region_kinds.md`** (or update if partially present) that:

- Enumerates **all** workbench region kinds and **all** inspector region kinds **supported in code today** (no invented kinds; no omissions).
- For each kind: required vs. optional payload fields; which **runtime** function/method emits it; which **client** branch in `v2_portal_shell.js` consumes it.
- Explains **`composition_mode`** and **foreground region** semantics as implemented (not as desired future behavior unless clearly flagged as non-contract aspirational).
- Clearly separates **shell composition contract** (what the shell state machine / runtime promises) from **presentation** (how the renderer chooses to lay out or style).

## Constraints that matter

- Derive semantics **from code**, not prompt history or archive narration (`agent/constraints.md` §2, §7).
- Preserve invariants: navigation/shell state serializable; tools attach via shell-defined surfaces; a UI widget is not a shell surface (`structural_invariants.md` / task `authority.notes`).
- Cite the task’s authority paths **inside** the contract doc where rules are restated.
- Keep “future tool extension” notes **short** and actionable per task YAML.

## Required outputs

1. **`MyCiteV2/docs/contracts/shell_region_kinds.md`** — canonical contract (path fixed in task `artifacts.contract_doc`).
2. **`reports/T-003-implementation.md`** — per `tasks/README.md` §9 (files changed, why, commands, tests, deploy N/A, gaps, recommended next status).
3. **`reports/handoffs/T-003/implementer_to_verifier.md`** — per README §8: files changed, commands, reports, risks, what verifier must check independently, recommended `status` / `execution` fields.

## Stop conditions

- Stop when acceptance bullets in the task YAML are satisfiable from the written doc + repo; do not refactor portal code unless the task scope is formally expanded.
- If the three files disagree on a kind or field, document the ambiguity and the code locations; do not silently pick one behavior as “the contract” without noting the conflict.

## Recommended next task state (after your work)

- Set `status` to **`verification_pending`**.
- Set `execution.current_role` to **`verifier`**.
- Set `execution.next_role` to **`lead`**.
- Leave `verification_result: pending` until verifier completes.

`repo_test_command` is `not_applicable`; run tests only if you touch executable code beyond docs (prefer doc-only change).
