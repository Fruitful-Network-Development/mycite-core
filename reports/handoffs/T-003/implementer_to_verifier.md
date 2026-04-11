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
