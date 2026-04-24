# Performance Weight/Speed Static Audit Report (2026-04-16)

Source plan: `docs/audits/performance_weight_speed_audit_plan_2026-04-16.md`.

## Maintenance-pass note (2026-04-20)

- Benchmark harness and deterministic fixtures are now present:
  - `scripts/benchmarks/build_weight.sh`
  - `scripts/benchmarks/runtime_interactions.sh`
  - `scripts/benchmarks/projection_serialization.py`
  - `benchmarks/data/*` with `CHECKSUMS.sha256`
  - generated baselines under `benchmarks/results/*_baseline.json`
- Low-risk hotspot remediation implemented:
  - `v2_portal_shell_core.js` now prefers `structuredClone` with safe fallback in `cloneRequest(...)`, replacing hot-path JSON clone-only behavior where supported.

## AWS-CSM Recovery Measurement Pass (2026-04-24)

Recovery-linked task: `TASK-AWS-CSM-RECOVERY-004`.

Scope:

- Measure current AWS-CSM panel/runtime projection latency against promoted FND
  private state.
- Trim repeat render-path overhead in the AWS-CSM workspace renderer without
  widening the authoritative write surface.

Observed runtime measurements (25 samples each, `run_portal_aws_csm(...)`
against `deployed/fnd/private`):

| Journey | Median | p95 | Min | Max |
|---|---:|---:|---:|---:|
| Domain gallery render (`view=domains`) | `10.53 ms` | `22.33 ms` | `9.05 ms` | `95.40 ms` |
| Domain route transition (`domain=cvccboard.org`) | `11.29 ms` | `18.61 ms` | `9.01 ms` | `22.05 ms` |
| Profile onboarding transition (`profile=aws-csm.cvccboard.nathan`, `section=onboarding`) | `10.89 ms` | `12.35 ms` | `8.98 ms` | `13.26 ms` |

Interpretation:

- These local source/runtime measurements are orders of magnitude below the
  reported 10-20 second AWS-CSM recovery baseline, which indicates the current
  repo-hosted render/projection path is not reproducing the historical deployed
  latency complaint.
- Remaining latency risk is therefore more consistent with deployment/runtime
  host conditions, network/browser load, or stale promoted assets than with the
  current repo-side AWS-CSM projection path itself.

Low-risk remediation completed in this pass:

- `v2_portal_aws_workspace.js` now uses one delegated `submit` listener and one
  delegated `click` listener on the workspace root instead of re-querying and
  re-binding per-control listeners on every rerender.
- Static post-change count:
  - delegated listeners: `submit=1`, `click=1`
  - direct `[data-aws-*]` `querySelectorAll(...)` rebinding loops: `0`

Parity/regression evidence:

- `MyCiteV2.tests.architecture.test_portal_one_shell_boundaries`
  now guards delegated AWS-CSM event binding and forbids regression back to the
  old repeated per-render listener-query pattern.

## 1) Static Hotspots (Concrete Targets)

### A. Asset weight hotspots (JS/static)

1. **Portal shell monolith payload**
   - Target: `MyCiteV2/instances/_shared/portal_host/static/portal.js`.
   - Static signal: largest single static shell script by line count (925 lines), suggesting startup parse/execute concentration and likely mixed concerns that could be split by surface/workspace boundary.
2. **System workspace renderer bundle concentration**
   - Target: `MyCiteV2/instances/_shared/portal_host/static/v2_portal_system_workspace.js`.
   - Static signal: high line count (563) and likely boot-path inclusion for system mode.
3. **Core shell orchestration + renderer fan-in**
   - Targets:
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_workbench_renderers.js`
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_inspector_renderers.js`
   - Static signal: boot/runtime composition code co-located with renderer dispatch; candidates for split by startup-critical vs deferred rendering regions.

### B. Rerender / repeated UI work hotspots

1. **Full subtree `innerHTML` replacement in control panel/activity regions**
   - Target: `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_region_renderers.js`.
   - Static signal: repeated `root.innerHTML = ...` and follow-up query/bind passes implies broad subtree invalidation and event rebinding per render.
2. **Shell composition path updates + multi-region render cascade**
   - Target: `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`.
   - Static signal: `applyChrome(...)` + `renderRegions(...)` choreography suggests synchronized updates across activity/control/workbench/inspector even when only one region changes.
3. **Workspace-specific renderers likely rebuilding full panels**
   - Targets:
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_system_workspace.js`
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_aws_workspace.js`
     - `MyCiteV2/instances/_shared/portal_host/static/v2_portal_network_workspace.js`
   - Static signal: module-level renderer files are large and likely regenerate DOM blocks from payloads each runtime update.

### C. Projection / serialization duplication hotspots

1. **Clone-by-serialization in shell core runtime loop**
   - Target: `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell_core.js`.
   - Static signal: repeated `JSON.parse(JSON.stringify(...))` in `cloneRequest`, canonical request construction, and history payload shaping.
2. **Contract `to_dict` / `from_dict` repetition across ports**
   - Targets:
     - `MyCiteV2/packages/ports/datum_store/contracts.py`
     - `MyCiteV2/packages/ports/audit_log/contracts.py`
     - `MyCiteV2/packages/ports/aws_read_only_status/contracts.py`
     - `MyCiteV2/packages/ports/network_root_read_model/contracts.py`
   - Static signal: highly repetitive model serialization adapters; candidate for shared canonical normalization helpers.
3. **State-machine shell serialization fan-out**
   - Target: `MyCiteV2/packages/state_machine/portal_shell/shell.py`.
   - Static signal: dense `to_dict()` conversion paths across shell request/state/composition models may duplicate normalization work across request lifecycle.
4. **Filesystem adapters with repeated read/parse/write JSON pipelines**
   - Targets:
     - `MyCiteV2/packages/adapters/filesystem/live_system_datum_store.py`
     - `MyCiteV2/packages/adapters/filesystem/live_aws_profile.py`
     - `MyCiteV2/packages/adapters/filesystem/aws_narrow_write.py`
     - `MyCiteV2/packages/adapters/filesystem/aws_csm_onboarding_profile_store.py`
     - `MyCiteV2/packages/adapters/filesystem/audit_log.py`
   - Static signal: similar JSON IO pipelines likely duplicate decode/validation/defaulting logic and intermediate allocations.
5. **High-volume projection composition in CTS GIS**
   - Target: `MyCiteV2/packages/modules/cross_domain/cts_gis/service.py`.
   - Static signal: large projection-building surface with document/row/feature transformations and repeated dict/list materialization patterns.

---

## 2) Baseline Measurement Placeholders + Thresholds

> This section intentionally defines **placeholders** and uses threshold language exactly from the audit plan section 2.

### A. Build/Weight Metrics

| Metric | Baseline Placeholder | Post-change Placeholder | Delta | Threshold / Rule |
|---|---:|---:|---:|---|
| Total JS shipped on initial load (raw) | `221,798 B` | `TBD_POST_RAW_KB` | `TBD_DELTA_%` | Track for trend + composition analysis |
| Total JS shipped on initial load (gzip) | `45,606 B` | `TBD_POST_GZIP_KB` | `TBD_DELTA_%` | **No regression rule:** Initial JS gzip must not increase by more than **+1%** from baseline. |
| Total JS shipped on initial load (brotli) | `TBD_BASELINE_BR_KB` | `TBD_POST_BR_KB` | `TBD_DELTA_%` | Monitor with gzip trend; explain divergence |
| Largest chunk #1..#5 (gzip) | `v2_portal_inspector_renderers.js (11,161B), portal.js (7,010B), v2_portal_aws_workspace.js (5,772B), v2_portal_system_workspace.js (4,728B), v2_portal_shell_region_renderers.js (4,439B)` | `TBD_POST_TOP5` | `TBD_DELTA_%` | **Chunk guardrail:** No new chunk over baseline largest chunk by more than **+5%** unless justified in RFC. |
| Parse + compile + execute time (initial scripts) | `TBD_BASELINE_PARSE_EXEC_MS` | `TBD_POST_PARSE_EXEC_MS` | `TBD_DELTA_%` | Tie improvements to chunking and startup critical-path split |
| Unused/duplicated module weight | `TBD_BASELINE_DUP_KB` | `TBD_POST_DUP_KB` | `TBD_DELTA_%` | **Improvement target:** Reduce initial JS gzip by **10–20%** in prioritized areas. |

### B. Runtime/Interaction Metrics

| Metric | Baseline Placeholder | Post-change Placeholder | Delta | Threshold / Rule |
|---|---:|---:|---:|---|
| Time-to-interactive-equivalent | `TBD_BASELINE_TTI_MS` | `TBD_POST_TTI_MS` | `TBD_DELTA_%` | Correlate with startup long tasks |
| Main-thread long tasks (startup + key interactions) | `TBD_BASELINE_LONGTASK_COUNT_MS` | `TBD_POST_LONGTASK_COUNT_MS` | `TBD_DELTA_%` | Must not regress user-visible responsiveness |
| Render commit duration (hotspot flows) | `TBD_BASELINE_RENDER_COMMIT_MS` | `TBD_POST_RENDER_COMMIT_MS` | `TBD_DELTA_%` | Prioritize high-frequency flows |
| Render count (audited screens) | `TBD_BASELINE_RENDER_COUNT` | `TBD_POST_RENDER_COUNT` | `TBD_DELTA_%` | **Render efficiency target:** Reduce redundant rerender count by **25%** on audited screens. |
| p95 interaction latency (top journeys) | `136.0` | `TBD_POST_P95_MS` | `TBD_DELTA_%` | **No regression rule:** p95 interaction latency must remain within **±5%** of baseline at minimum. |
| p95 interaction latency (selected hotspots) | `136.0` | `TBD_POST_HOTSPOT_P95_MS` | `TBD_DELTA_%` | **Improvement target:** p95 interaction latency reduced by **15%** for selected hotspots. |

### C. Projection/Serialization Metrics

| Metric | Baseline Placeholder | Post-change Placeholder | Delta | Threshold / Rule |
|---|---:|---:|---:|---|
| End-to-end time in projection helpers (representative flows) | `median 0.039ms / p95 0.103ms` | `TBD_POST_PROJECTION_CPU_MS` | `TBD_DELTA_%` | **No regression rule:** CPU time in critical projection path does not increase over baseline. |
| Allocation count/bytes in transformation pipelines | `425 B avg payload` | `TBD_POST_ALLOC_COUNT_BYTES` | `TBD_DELTA_%` | **Allocation target:** Reduce intermediate object allocations by **20%** in audited pathways. |
| Serialization/deserialization CPU cost + invocation frequency | `TBD_BASELINE_SERDE_CPU_FREQ` | `TBD_POST_SERDE_CPU_FREQ` | `TBD_DELTA_%` | **Improvement target:** Reduce projection+serialization CPU time by **20%** on top 3 hotspots. |

### D. Measurement Hygiene Placeholders (must be filled in Code mode)

- Dataset ID/version: `portal_shell_fixture_v1 / cts_gis_projection_fixture_v1 / interaction_journeys_v1`
- Scenario script set: `scripts/benchmarks/build_weight.sh`, `scripts/benchmarks/runtime_interactions.sh`, `scripts/benchmarks/projection_serialization.py`
- Iteration count per benchmark: `250` (projection), fixture-bound for interaction journeys
- Reported stats: `median` + `p95` (required)
- Environment metadata capture:
- machine profile: `linux 6.12.63+deb13-cloud-amd64`
- runtime version(s): `python3 + shell scripts`
- commit SHA: `TBD_COMMIT_SHA`
- Baseline vs post storage path: `benchmarks/results/*_baseline.json`

---

## 3) Top-10 Backlog (Impact vs Risk Ranked)

| Rank | Item | Category | Expected Impact | Risk | Evidence Needed | Owner | Status |
|---:|---|---|---|---|---|---|---|
| 1 | Split `portal.js` into startup-critical shell boot + deferred workspace chunks | Asset Weight | High (startup parse/execute reduction; gzip drop) | Medium | Bundle composition diff + startup timing trace | TBD | Planned |
| 2 | Add region-level render diffing to avoid full `innerHTML` replacement for stable control-panel sections | Render Pass | High (rerender count reduction) | Medium | Render count instrumentation + DOM mutation profile | TBD | Planned |
| 3 | Introduce canonical lightweight clone helper and remove hot-path `JSON.parse(JSON.stringify(...))` usage | Projection/Serialization | High (CPU + allocation reduction) | Medium | CPU profile around shell request/history flow + parity tests | TBD | Planned |
| 4 | Consolidate repeated contract serialization helpers for shared field normalization primitives | Projection/Serialization | Medium-High (duplication + maintainability) | Medium | Static dedupe map + contract snapshot parity | TBD | Planned |
| 5 | Extract lazy-loaded workspace renderer modules by active service boundary (system/aws/network) | Asset Weight | High (initial weight reduction) | Medium | Route/workspace load waterfall + chunk diff | TBD | Planned |
| 6 | Cache stable projection fragments in CTS GIS row/document projection pipeline | Projection | High (projection CPU reduction on repeat navigation) | High | Flow-level projection timing + allocation profile | TBD | Planned |
| 7 | Normalize filesystem adapter JSON IO through shared serializer/deserializer utility | Serialization | Medium (CPU + consistency + reduced duplication) | Medium | IO profile + contract tests for persisted payloads | TBD | Planned |
| 8 | Add memoization/identity stabilization for shell composition and region context objects | Render Pass | Medium (lower unnecessary rerender/rebind work) | Medium | Instrumented rerender counts + key interaction latency | TBD | Planned |
| 9 | Replace repeated inline SVG/markup generation with cached template fragments for activity/control surfaces | Render Pass | Medium (DOM construction cost reduction) | Low | Startup + navigation microbench + mutation count | TBD | Planned |
| 10 | Remove dead or duplicate static renderer code paths after migration coverage threshold is met | Asset Weight | Medium (shipped bytes + parse cost) | High | Dead-code report + usage telemetry + rollback drill | TBD | Planned |

---

## 4) Risk Controls Per Backlog Item

### 1) Split `portal.js` into startup + deferred chunks
- Tests: shell boot integration tests + smoke navigation for system/aws/network surfaces.
- Isolation strategy: feature flag `portal_startup_chunk_v2`; dual-load fallback path retained.
- Regression gates: CI bundle budget check + boot success rate gate.
- Rollback path: disable flag; serve previous monolith script.

### 2) Region-level render diffing
- Tests: deterministic DOM snapshot tests for control panel + activity bar; interaction click-path tests.
- Isolation strategy: introduce renderer adapter layer preserving existing contract shape.
- Regression gates: rerender count benchmark must improve; no accessibility role/name regressions.
- Rollback path: renderer switch toggled back to full-replace mode.

### 3) Replace JSON clone hot paths
- Tests: canonical request/history payload golden tests; deep-equality semantics tests for clone helper.
- Isolation strategy: shim `cloneRequest` implementation first, then incremental callsite migration.
- Regression gates: projection CPU no-regression check; payload parity required in CI.
- Rollback path: revert helper usage to current clone implementation.

### 4) Consolidate contract serialization primitives
- Tests: snapshot tests of all affected `to_dict`/`from_dict` outputs; schema contract tests.
- Isolation strategy: shared helper module with compatibility wrappers per port.
- Regression gates: unchanged serialized payload corpus on fixture set.
- Rollback path: keep wrappers; re-route affected contracts to legacy logic.

### 5) Lazy-load workspace renderer modules
- Tests: service-switch integration tests + fallback handling tests when deferred chunk load fails.
- Isolation strategy: progressive rollout by service (system first, then aws, then network).
- Regression gates: chunk-size budget + interaction latency guardrails.
- Rollback path: pre-load all workspace modules synchronously.

### 6) Cache CTS GIS projection fragments
- Tests: projection determinism tests across document/row permutations; invalidation-path tests.
- Isolation strategy: cache keyed by explicit projection input signature; bounded cache policy.
- Regression gates: no stale-data incidents in regression suite; CPU improvement evidence required.
- Rollback path: disable cache with runtime flag; revert to uncached projection.

### 7) Shared JSON IO utility for filesystem adapters
- Tests: adapter contract tests for read/write roundtrip; corruption-handling tests.
- Isolation strategy: introduce utility opt-in per adapter one at a time.
- Regression gates: persisted payload compatibility checks + audit log read/write parity.
- Rollback path: adapter-local serializer paths remain available.

### 8) Memoize shell composition/region context
- Tests: UI state transition tests ensuring visible state consistency; memo invalidation tests.
- Isolation strategy: memoization bounded to stable keys; no hidden global cache state.
- Regression gates: rerender reduction + p95 latency no-regression.
- Rollback path: disable memo layer and use current object recreation path.

### 9) Cache SVG/markup template fragments
- Tests: visual DOM snapshot tests for icon/label states; click handler preservation tests.
- Isolation strategy: pure template cache utility without changing renderer contract.
- Regression gates: DOM mutation count reduction on repeated navigation.
- Rollback path: switch renderer back to per-render markup generation.

### 10) Remove dead/duplicate renderer code
- Tests: coverage + runtime smoke for all declared surfaces before deletion.
- Isolation strategy: deprecate then remove in separate commits.
- Regression gates: usage telemetry confirms zero hits over agreed window.
- Rollback path: restore archived module path from tagged release.

---

## 5) “Ready for Code mode” Criteria

Code mode execution may begin only when **all** criteria below are met:

1. **Benchmark scripts defined and reviewed**
   - Required scripts (minimum set):
     - `scripts/benchmarks/build_weight.sh` (bundle/raw/gzip/brotli + largest chunks)
     - `scripts/benchmarks/runtime_interactions.sh` (startup long tasks + p95 interaction)
     - `scripts/benchmarks/projection_serialization.py` (projection CPU + allocation metrics)
2. **Deterministic benchmark datasets available**
   - Required data artifacts:
     - `benchmarks/data/portal_shell_fixture_v1.json`
     - `benchmarks/data/cts_gis_projection_fixture_v1.json`
     - `benchmarks/data/interaction_journeys_v1.json`
   - Each artifact must have documented schema version and checksum.
3. **Baseline capture complete**
   - Baseline metrics for all section 2 tables populated with commit SHA and environment metadata.
4. **Regression gates wired**
   - CI checks configured for: bundle budget, p95 latency guardrail, projection CPU no-regression, contract parity tests.
5. **Approval gate passed (required)**
   - Approval sign-off from:
     - Engineering owner for target modules.
     - Runtime/performance reviewer validating benchmark methodology.
     - QA reviewer confirming regression suite coverage.
   - Execution starts only after explicit “Code mode approved” acknowledgment in audit thread.
