# Workbench UI Utilitarian Design Audit

Date: 2026-04-21

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-23`

## Purpose

Verify the current `workbench_ui` surface against the intended utilitarian benchmark: clear cut, spreadsheet-like, low visual heaviness, additive overlays only, sturdy control panel behavior, and good modular separation between runtime, service, and presentation payload building.

## Scope

Code and doc scope:

- `MyCiteV2/packages/tools/workbench_ui/README.md`
- `MyCiteV2/packages/tools/workbench_ui/service.py`
- `MyCiteV2/instances/_shared/runtime/portal_workbench_ui_runtime.py`
- `MyCiteV2/tests/unit/test_workbench_ui_runtime.py`
- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/surface_catalog.md`

## Benchmark Review

| Benchmark | Status | Evidence | Deficiency |
|---|---|---|---|
| clear cut | `met` | the surface is explicitly read-only, SQL-backed, and bounded to a dedicated tool/runtime path | none blocking |
| spreadsheet-like | `met` | the two-pane document table plus datum grid now includes sticky headers, explicit selected-row markers, grouping modes, interpreted/raw lenses, and query-driven navigation | none blocking |
| low visual heaviness | `met` | the payload is text-first, section-led, and does not introduce ornamental or multi-mode chrome | none blocking |
| additive overlays only | `met` | overlays are read after semantic resolution, summarized separately, and tested as non-mutating; source and overlay visibility are independently query-driven | none blocking |
| sturdy control panel behavior | `met` | control entries, selection summaries, and next/previous actions are canonical-query backed and shell-request backed | saved query bundles remain intentionally deferred |
| modular separation | `met` | `WorkbenchUiReadService` owns data reads/filter/sort, while the runtime owns shell projection and control-panel composition | none blocking |

## Findings

1. The current surface already matches the intended utilitarian direction better than a bespoke app shell would.
   - It is shell-attached, script-backed, SQL-read driven, and clearly read-only.
   - It remains separate from the reducer-owned `SYSTEM` anthology workspace rather than replacing `/portal/system`.

2. The current SQL authority inspector is structurally sound as an operator work surface.
   - The document table and datum grid are present.
   - Sticky headers, explicit selection markers, grouping modes, interpreted/raw lenses, short identity badges, and query-driven navigation are already part of the current payload/runtime contract.
   - Fresh `workbench_ui` load may intentionally land on a CTS-GIS authoritative document without changing the reducer-owned `SYSTEM` default.

3. Additive-only overlay behavior is already correctly constrained.
   - Overlay reads are separate from authoritative datum rows.
   - Tests confirm that overlay inspection does not mutate row payloads.

4. The next practical gating concerns now live in CTS-GIS data assurance rather than `workbench_ui` architecture.
   - SQL/filesystem parity and row-graph integrity need to remain explicit and reproducible.
   - HOPS/source visual correctness, the blocked missing source profile `3-2-3-17-77-1-14`, and runtime provenance/readiness warnings remain the meaningful CTS-GIS concerns.

## Next Steps

- implement the follow-on plan in `docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md`
- keep `SYSTEM` and `workbench_ui` distinct in active docs and contracts
- keep `workbench_ui` shell-attached, script-backed, read-only, and additive-only as the SQL authority inspector under `SYSTEM`
- use `docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md` as the blocking CTS-GIS parity/readiness gate before more CTS-GIS feature work

## Verification

Planned verification for this pass:

- `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`
- `python3 -m unittest MyCiteV2.tests.unit.test_mos_program_closure`

## Result

`workbench_ui` already passes the current utilitarian benchmark on architecture, posture, and additive-only behavior. The remaining meaningful gating work now sits in CTS-GIS provenance/readiness assurance rather than in a `workbench_ui` redesign.

## 2026-04-23 Maintenance Refresh

- Revalidated that `workbench_ui` remains shell-attached, read-only, additive-only,
  and does not introduce a parallel frontend stack.
- Re-ran:
  - `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`
  - `python3 -m unittest MyCiteV2.tests.unit.test_mos_program_closure`
- Result: both suites pass, maintaining bounded post-closure scope posture.
