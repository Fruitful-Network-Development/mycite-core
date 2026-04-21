# Workbench UI Utilitarian Design Audit

Date: 2026-04-21

Doc type: `audit`
Normativity: `supporting`
Lifecycle: `completed`
Last reviewed: `2026-04-21`

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
| spreadsheet-like | `partially met` | the two-pane document table plus datum grid already gives a utilitarian sheet posture | no keyboard navigation, no frozen-header contract, and no explicit selected-datum-row marker |
| low visual heaviness | `met` | the payload is text-first, section-led, and does not introduce ornamental or multi-mode chrome | hash-heavy columns will become visually noisy as the table scales |
| additive overlays only | `met` | overlays are read after semantic resolution, summarized separately, and tested as non-mutating | overlay visibility exists, but source visibility does not |
| sturdy control panel behavior | `partially met` | control entries are canonical-query backed and shell-request backed | there is no compact selection-state summary for the active datum row and no simple saved query bundles |
| modular separation | `met` | `WorkbenchUiReadService` owns data reads/filter/sort, while the runtime owns shell projection and control-panel composition | presentation payload shaping is still split across service/runtime and could become harder to extend if more display modes are added |

## Findings

1. The current surface already matches the intended utilitarian direction better than a bespoke app shell would.
   - It is shell-attached, script-backed, SQL-read driven, and clearly read-only.

2. The current datum-file workbench is structurally sound but still shallow as an operator work surface.
   - The document table and datum grid are present.
   - The workbench lens is effectively the inspector, but it does not yet expose an explicit raw-versus-interpreted toggle.

3. Additive-only overlay behavior is already correctly constrained.
   - Overlay reads are separate from authoritative datum rows.
   - Tests confirm that overlay inspection does not mutate row payloads.

4. The next practical weaknesses are clarity and navigation rather than architecture.
   - No keyboard navigation contract exists.
   - No frozen-header or sticky-selection affordance is modeled.
   - No grouping controls exist for `layer` / `value_group`.
   - `version_hash` and `hyphae_hash` are exposed as raw long strings rather than compact semantic identity badges.
   - Source visibility controls are missing; only overlay visibility is modeled today.

## Next Steps

- implement the follow-on plan in `docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md`
- keep the datum-file workbench shell-attached, script-backed, read-only, and additive-only
- prioritize keyboard navigation, selection clarity, grouping, workbench-lens toggles, and semantic identity badges before any saved query presets

## Verification

Planned verification for this pass:

- `python3 -m unittest MyCiteV2.tests.unit.test_workbench_ui_runtime`

## Result

`workbench_ui` already passes the core utilitarian benchmark on architecture, posture, and additive-only behavior. The remaining work is modest hardening of navigation, grouping, and inspection clarity rather than a redesign or framework change.
