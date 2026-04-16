# Desktop Access Historical Drift Report

Date: 2026-04-16  
Source plan: `docs/audits/desktop_access_and_historical_drift_audit_plan_2026-04-16.md`

## Compatibility Inventory (Section 2)

| ID | Module/File | Assumption Category | Current Behavior | Desktop Impact / Severity | Remediation Boundary | Owner / Phase |
|---|---|---|---|---|---|---|
| CI-01 | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js` | url | URL state sync relies on browser history (`pushState` / `replaceState`) from canonical envelope URLs. | **High**: desktop host needs startup URL translation and back/forward bridge; otherwise deep-link and history parity break. | adapter + test | Runtime + Host team / **Phase 2** |
| CI-02 | `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js` | process | Fatal path assumes browser script-loader lifecycle (`document.createElement('script')` + onload chain). | **Medium**: desktop bootstrap wrappers that inject bundles differently can misclassify successful startup as fatal. | adapter + config + test | Host team / **Phase 2** |
| CI-03 | `MyCiteV2/instances/_shared/portal_host/static/portal.js` | storage | Shell chrome/theme widths and toggle state persist to `window.localStorage`. | **High**: desktop multi-window/session can diverge or race when sharing one storage namespace; persistence unavailable in hardened contexts. | adapter + core + test | Host + State team / **Phase 1** |
| CI-04 | `MyCiteV2/packages/adapters/filesystem/live_system_datum_store.py` | path | Data contract assumes canonical folder layout under a provided `data_dir` (`system/anthology.json`, `system/sources`, `payloads/cache`, `sandbox/*/sources`). | **Critical**: desktop packaging or relocated writable roots can fail reads/writes if layout is not capability-routed. | adapter + config + test | Data platform / **Phase 1** |
| CI-05 | `MyCiteV2/packages/adapters/filesystem/audit_log.py` | storage | Audit writes append NDJSON to a single filesystem target with no explicit cross-process lock/rotation strategy. | **High**: desktop multi-process or multi-window writers can produce contention/corruption risk. | adapter + core + test | Platform runtime / **Phase 1** |
| CI-06 | `MyCiteV2/packages/adapters/filesystem/network_root_read_model.py` | path | Read model recursively scans JSON trees from local disk roots and assumes direct file access availability. | **Medium**: desktop offline mode is compatible, but path remapping/sandbox permissions can silently narrow available evidence. | adapter + config | Data platform / **Phase 2** |
| CI-07 | `MyCiteV2/instances/_shared/portal_host/templates/portal.html` | ui | Menubar controls and layout semantics are web-first and do not negotiate native menu accelerator ownership. | **High**: conflicting keyboard accelerators between web handlers and native shell can produce nondeterministic actions. | adapter + ui + test | Host + UX / **Phase 2** |
| CI-08 | `MyCiteV2/packages/state_machine/portal_shell/shell.py` | url | Canonical routes are centralized (`/portal/system`, `/portal/network`, `/portal/utilities`, tool routes) and query normalization is runtime-owned. | **Low (positive anchor)**: strong baseline for desktop parity; risk is only in host translation layers. | test + docs | State machine / **Phase 0** |
| CI-09 | `MyCiteV2/instances/_shared/runtime/portal_shell_runtime.py` | process | Integration flags are path-existence checks (`Path(...).exists()`) for optional integrations, not process-health probes. | **Medium**: desktop can report “operational” mismatch if processes fail after boot despite valid paths. | adapter + test | Runtime integrations / **Phase 2** |

### Inventory Notes

- Section 2 categories were fully covered: **path, process, url, storage, ui**.
- The highest-risk blockers for desktop posture are CI-04 and CI-05 (filesystem layout + concurrent write behavior).

## Drift Matrix (Section 3): Legacy Intent vs Current Behavior

| ID | Legacy Intent | Current Behavior | Drift Class | Severity | Evidence Anchor | Reconciliation Action | Acceptance Criteria |
|---|---|---|---|---|---|---|---|
| DM-01 | One canonical shell authority regardless of host form factor. | `portal_shell` keeps canonical surface IDs, routes, transitions, and reducer-owned boundaries. | intent preserved | Low | `portal_shell/shell.py` canonical constants and reducer-owned sets. | keep as-is | Contract tests pass for same request body across web + desktop adapters with identical canonical URL + shell state projection. |
| DM-02 | Deep-link entry must restore user into canonical `SYSTEM` context on startup. | Web host updates history via runtime envelope; desktop startup translation path is not yet explicit. | narrowed | **High** | Browser `pushState`/`replaceState` usage in core shell runtime. | **shim** | Desktop deep-link `/portal/system/tools/<slug>?...` maps to one canonical shell request before first render; parity tests assert same surface_id and query projection as web. |
| DM-03 | Legacy aliases remain intake-compatible during migration windows. | CTS-GIS legacy alias and anchor compatibility are still present and warning-instrumented in datum store adapter. | intent preserved | Medium | Legacy compat helpers in datum store adapter (`cts_gis_legacy_compat`). | keep as-is | Legacy inputs resolve to canonical IDs and emit structured warning code; no second routing authority introduced. |
| DM-04 | Runtime state persistence should remain deterministic across sessions. | Browser localStorage persistence exists, but no explicit multi-window conflict mediation for desktop host sessions. | narrowed | **High** | `portal.js` localStorage keys for theme/layout/toggles. | **restore** | Introduce scoped storage provider (window/session namespace + conflict policy); parallel window tests show deterministic last-writer policy and no corrupted layout state. |
| DM-05 | Filesystem-backed reads/writes should be portable under packaging changes. | Store adapters use fixed relative layout assumptions under `data_dir`; no manifest-driven path indirection yet. | broken | **Critical** | Datum store + read model adapter path conventions. | **shim** | Add capability-routed path provider; test matrix validates identical functional outputs for default layout and packaged-remapped layout. |
| DM-06 | Audit/event logs should remain append-safe in concurrent usage contexts. | Single-file append adapter with no explicit cross-process lock protocol. | broken | **High** | Audit log adapter append flow. | **restore** | Add lock-safe append strategy (or host journal abstraction) and stress tests with concurrent writers proving no malformed lines or record loss. |
| DM-07 | Browser-only keyboard semantics should not conflict with native host accelerators. | Current shell controls are DOM-first; native menu ownership map is unspecified. | narrowed | **High** | Menubar and shell toggle controls in `portal.html` + JS modules. | **retire with migration** | Publish accelerator ownership table; migrate conflicting shortcuts to native-first map with documented web fallback; UX verification confirms no duplicate trigger paths. |
| DM-08 | Split-shell historical routes should not persist as active behavior. | One-shell route set is canonical and documented; split-shell paths are absent from active route constants. | obsolete | Low | Current docs/contracts and route constants. | retire with migration | Maintain deprecation note and redirect/no-op policy for any legacy bookmarks; telemetry confirms near-zero legacy route traffic before removal. |

## Phase 0–3 Work Mapping (Section 5)

| Accepted Work Item | Source Rows | Phase | Target Sprint | Dependencies / Notes |
|---|---|---|---|---|
| Build desktop compatibility inventory + executable parity baseline | CI-01..CI-09, DM-01 | Phase 0 | Sprint P0-S1 | Requires contract test harness capable of replaying shell requests against web and desktop adapter stubs. |
| Deep-link startup translation shim | DM-02 | Phase 1 (contract-critical) with Phase 2 integration hardening | Sprint P1-S1 (shim) + P2-S1 (host integration) | Depends on canonical shell request factory and desktop boot hook injection point. |
| Scoped persistence provider for shell chrome/theme state | CI-03, DM-04 | Phase 1 | Sprint P1-S2 | Depends on storage abstraction interface and migration for existing localStorage keys. |
| Capability-routed data path provider | CI-04, DM-05 | Phase 1 | Sprint P1-S1 | Blocks desktop packaging portability; requires adapter contract and fixture layout matrix. |
| Concurrent-safe audit append strategy | CI-05, DM-06 | Phase 1 | Sprint P1-S2 | Depends on lock/journal approach decision (OS lock vs host service). |
| Native/web accelerator ownership reconciliation | CI-07, DM-07 | Phase 2 | Sprint P2-S1 | Depends on desktop shell API constraints and UX sign-off. |
| Integration-health truthfulness (path exists vs process health) | CI-09 | Phase 2 | Sprint P2-S1 | Requires optional health probe contract for adapters. |
| Sunset old route assumptions + telemetry deprecation gate | DM-08 | Phase 3 | Sprint P3-S1 (start), ongoing cleanup | Depends on telemetry instrumentation and published migration window. |

## Exit Criteria Status

| Exit Criterion (Section 5) | Status | Notes |
|---|---|---|
| All critical/high findings resolved or accepted with explicit waivers. | **At risk / open** | Critical/high findings are identified; reconciliation actions defined, not yet implemented. |
| Contract test suite demonstrates parity for agreed historical behaviors. | **Open** | Parity suite expansion is planned in Phase 0 and Phase 1. |
| Desktop and web variants share one canonical state/routing authority. | **Partially met** | Core runtime/state machine is canonical; desktop-specific translation/accelerator handling still pending. |
| Remaining compatibility paths have owners, sunset dates, and telemetry. | **Partially met** | Owners/phases assigned; sunset dates/telemetry thresholds still to be ratified in Phase 3. |

## Unresolved Risks (Explicit)

1. **Packaging path indirection risk**: if desktop installer moves writable paths without a capability provider, canonical datum documents can become non-discoverable.
2. **Concurrent write integrity risk**: single-file audit append behavior may fail under simultaneous desktop windows/processes.
3. **History/deep-link divergence risk**: browser history semantics may not map 1:1 to native navigation lifecycle without a translation shim.
4. **Accelerator collision risk**: duplicate shortcut bindings between web JS and native menu can trigger conflicting shell actions.
5. **Operational false-positive risk**: path-existence integration checks may claim tools are healthy even when backing process/services are unavailable.
