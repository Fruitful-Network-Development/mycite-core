# T-003 Implementation report

## 1. Files changed

| File | Change type |
|------|-------------|
| `MyCiteV2/docs/contracts/shell_region_kinds.md` | documentation (contract) |
| `MyCiteV2/docs/contracts/README.md` | documentation (cross-link) |
| `reports/T-003-implementation.md` | documentation (this report) |
| `reports/handoffs/T-003/implementer_to_verifier.md` | documentation (handoff) |
| `tasks/T-003-shell-region-contracts.yaml` | documentation (lifecycle state) |

## 2. Why each file changed

- **`shell_region_kinds.md`:** Canonical contract for workbench and inspector `kind` values, per-region field tables, `composition_mode` / `foreground_shell_region` / inspector collapse semantics, activity bar and control_panel wire shapes, explicit separation of shell composition vs JS presentation, and mapping from `admin_shell.py` / `admin_runtime.py` / `v2_portal_shell.js`. Includes note that `_inspector_json` (`json_document`) is not on the live emission path.
- **`docs/contracts/README.md`:** Lead handoff asked alignment with existing contract index; added one bullet linking the new doc.
- **Reports and handoff:** Required task artifacts for verifier handoff.
- **Task YAML:** Advance lifecycle to `verification_pending` and assign verifier per `tasks/README.md` and lead handoff.

## 3. Commands run

None required (`execution.repo_test_command: not_applicable`). No code changes.

## 4. Tests run

Not applicable (documentation-only task).

## 5. Deploy actions taken

Not applicable (`primary_type: repo_only`).

## 6. Remaining gaps / unresolved risks

- **`json_document` inspector kind:** Supported in JS and by `_inspector_json` in Python, but no `run_admin_shell_entry` path emits it. Documented explicitly so the verifier can confirm intentional gap vs omission.
- **Verifier** should grep the three scoped files once more for any `kind` string not listed (e.g. future edits on other branches).

## 7. Recommended next status

`status: verification_pending`, `execution.current_role: verifier`, `execution.next_role: lead`, `verification_result: pending` (unchanged until verifier acts).

# Verifier → Lead: T-003

## Exact verification commands used

```bash
cd /srv/repo/mycite-core && grep -n '"kind":' MyCiteV2/instances/_shared/runtime/admin_runtime.py; echo '---'; grep -n 'kind ===' MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js; echo '---'; grep -n '_inspector_json' MyCiteV2/instances/_shared/runtime/admin_runtime.py
```

Plus targeted file reads of `shell_region_kinds.md`, `admin_shell.py` (composition builders and mode helpers), and the bodies of `_build_regions_and_surface`, `_apply_shell_chrome_to_composition`, `_activity_items`, `_control_panel_region` in `admin_runtime.py`.

## Exact evidence summary

- All workbench region `kind` values emitted on the live path appear in `shell_region_kinds.md` and have corresponding `renderWorkbench` branches.
- All inspector region `kind` values emitted on the live path appear in the main inspector table with matching `renderInspector` branches.
- `json_document` exists only as `_inspector_json` (definition only, no call sites) and as a JS branch; the contract’s “reserved, not live-emitted” classification is correct.
- `composition_mode`, `foreground_shell_region`, and chrome override for `tool_collapsed_inspector` match `admin_shell.py` + `_apply_shell_chrome_to_composition` + `applyChrome`.

## Pass/fail verdict

**pass**

## Mismatches found

None that block closure. Optional documentation tightening: the workbench `error` row could explicitly list all `_workbench_error` use cases (Datum/AWS/unhandled surface) so “selection-blocked paths” is not read as the only source of `error` payloads.

## Recommended final status

`verified_pass` with `verification_result: pass`; lead may mark `status: resolved` when satisfied with `closure_rule`.

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

# Implementer → Verifier: T-003

## Files changed

- `MyCiteV2/docs/contracts/shell_region_kinds.md` (new)
- `MyCiteV2/docs/contracts/README.md` (link to new contract)
- `reports/T-003-implementation.md`
- `tasks/T-003-shell-region-contracts.yaml` (lifecycle)

## Commands run

None (`repo_test_command: not_applicable`).

## Reports written

- `reports/T-003-implementation.md`
- This handoff file

## Unresolved risks

- Contract explicitly documents that inspector `json_document` is rendered in JS and built by `_inspector_json` but **not emitted** by `run_admin_shell_entry` today. Verifier should confirm that classification matches their reading of `admin_runtime.py`.

## What must be independently verified

1. Every **workbench** `kind` emitted by `_build_regions_and_surface` / `_apply_shell_chrome_to_composition` appears in `shell_region_kinds.md` with accurate fields and client branch mapping.
2. Every **inspector** `kind` emitted on live paths appears with the same checks.
3. No **documented** workbench/inspector `kind` is invented without a matching string in Python or JS (whichever side owns emission vs consumption).
4. **No emitted** `kind` is missing from the doc (including `tool_collapsed_inspector`, `banner` on registry workbench, nested block `kind` in `home_summary` clarified as non–region-kind).
5. `composition_mode`, `foreground_shell_region`, and inspector collapse behavior match `admin_shell.py`, `_apply_shell_chrome_to_composition`, and `applyChrome`.

## Recommended next task status

After verification: verifier sets `verified_pass` or `verified_fail` per `tasks/README.md`; lead resolves closure.

# T-003 Verification report

## 1. Exact commands used

```bash
cd /srv/repo/mycite-core && grep -n '"kind":' MyCiteV2/instances/_shared/runtime/admin_runtime.py; echo '---'; grep -n 'kind ===' MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js; echo '---'; grep -n '_inspector_json' MyCiteV2/instances/_shared/runtime/admin_runtime.py
```

Manual cross-read (no additional commands): `MyCiteV2/docs/contracts/shell_region_kinds.md`, `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` (`build_shell_composition_payload`, `shell_composition_mode_for_surface`, `foreground_region_for_surface`, `inspector_collapsed_for_surface`, `build_portal_activity_dispatch_bodies`), `admin_runtime.py` (`_build_regions_and_surface`, `_apply_shell_chrome_to_composition`, `_control_panel_region`, `_activity_items`), `reports/T-003-implementation.md`, `reports/handoffs/T-003/implementer_to_verifier.md`.

## 2. Exact captured stdout/stderr

```
257:        "kind": "error",
270:        {"kind": "metric", "label": "Admin audit", "value": _as_text(audit.get("status")) or "—"},
271:        {"kind": "metric", "label": "Shell entry", "value": _as_text(readiness.get("shell_entry")) or "—"},
272:        {"kind": "metric", "label": "Tool registry", "value": _as_text(readiness.get("tool_registry")) or "—"},
276:        "kind": "home_summary",
289:        "kind": "tool_registry",
302:        "kind": "datum_workbench",
322:        "kind": "empty",
331:        "kind": "json_document",
341:        "kind": "aws_read_only_surface",
366:        "kind": "aws_tool_error",
390:                "kind": "tool_collapsed_inspector",
410:        "kind": "narrow_write_form",
451:                "kind": "tool_registry",
559:                "kind": "tool_placeholder",
587:            "kind": "tool_placeholder",
---
194:    if (kind === "hidden" || wb.visible === false) {
198:    if (kind === "error") {
207:    if (kind === "home_summary") {
226:    if (kind === "tool_registry") {
257:    if (kind === "datum_workbench") {
301:    if (kind === "tool_collapsed_inspector") {
310:    if (kind === "tool_placeholder") {
328:    if (kind === "empty") {
332:    if (kind === "json_document") {
337:    if (kind === "aws_read_only_surface") {
376:    if (kind === "aws_tool_error") {
392:    if (kind === "narrow_write_form") {
---
327:def _inspector_json(*, title: str, document: dict[str, Any] | None) -> dict[str, Any]:
```

`_inspector_json` appears only at its definition; there is no call site in this file, consistent with the contract’s claim that `json_document` is not on the live emission path through `run_admin_shell_entry`.

## 3. Acceptance mapping: pass/fail by criterion

| Criterion | Verdict | Notes |
|-----------|---------|--------|
| Contract doc exists at `MyCiteV2/docs/contracts/shell_region_kinds.md` | **pass** | File present and linked from `docs/contracts/README.md`. |
| Enumerates all currently supported workbench kinds | **pass** | Region-level workbench kinds emitted by `_build_regions_and_surface` / `_apply_shell_chrome_to_composition`: `error`, `home_summary`, `tool_registry`, `datum_workbench`, `tool_placeholder`, `tool_collapsed_inspector`. Nested `metric` in `home_summary.blocks` correctly described as non–region-kind. |
| Enumerates all currently supported inspector kinds (live) | **pass** | Emitted: `empty`, `aws_read_only_surface`, `aws_tool_error`, `narrow_write_form`. `json_document` documented separately as reserved / not emitted; matches grep (no `_inspector_json` usage). |
| Required and optional fields per kind | **pass** | Spot-checked `aws_read_only_surface` and `_inspector_aws_read_only_surface`; tables align with returned dict keys. |
| Runtime function per kind | **pass** (minor ambiguity) | Mappings match code. The `error` row’s emitter text mentions `_workbench_error` and “selection-blocked paths” but does not name every `_workbench_error` branch (e.g. Datum misconfig, AWS tool failure, unknown surface); function name is still correct. |
| Client renderer branch per kind | **pass** | Each emitted workbench/inspector kind has a matching `renderWorkbench` / `renderInspector` branch; `hidden` + `visible === false` behavior matches JS. |
| Shell composition vs presentation | **pass** | Separation and `AdminShellChrome` / `requested_shell_chrome` notes match `admin_shell.py` and `_apply_shell_chrome_to_composition`. |
| No invented kinds; no emitted kind omitted | **pass** | No doc-only region `kind` without Python or JS support; no Python-emitted region `kind` missing from the contract tables (with `json_document` correctly classified as non-live). |

## 4. Repo/host/live mismatches

- **Repo:** None material. Optional doc polish: expand the `error` workbench row to say “any path that returns `_workbench_error(...)`” so readers do not infer only selection-blocked errors.
- **Host:** not applicable (`primary_type: repo_only`).
- **Live:** not applicable (`live_check_command: not_applicable`).

## 5. Final verdict

**pass** — Contract matches current `admin_shell.py`, `admin_runtime.py`, and `v2_portal_shell.js` for supported shell region kinds and top-level composition semantics, with `json_document` correctly scoped as non-emitted.

## 6. Recommended next status

Lead may set `status: resolved` after closure review per `closure_rule` in `tasks/T-003-shell-region-contracts.yaml`. Recommended task fields after lead action: `status: resolved`, `verification_result: pass` (unchanged), `execution.current_role` / `next_role` per lead workflow.
