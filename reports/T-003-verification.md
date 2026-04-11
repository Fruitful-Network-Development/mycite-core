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
