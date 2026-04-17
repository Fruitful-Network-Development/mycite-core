# Performance Weight/Speed Audit Plan (2026-04-16)

## Scope and Intent

This audit plan defines how to identify and prioritize performance opportunities that reduce runtime cost and shipped weight while preserving behavior. The plan focuses on static hotspots visible from source/build artifacts and a follow-up measurement phase to be executed in Code mode.

---

## 1) Static Hotspots to Target

### A. Large JavaScript Assets

Identify sources of byte-size and parse/execute overhead:

- Oversized entry bundles and route chunks (especially shared vendor chunks).
- Duplicate package inclusions caused by inconsistent import paths or multiple versions.
- High-cost utility libraries imported for small feature slices.
- Serialization/formatting libs loaded in hot paths where lighter alternatives exist.
- Non-critical code loaded at startup instead of on-demand.

**Static signals to collect**

- Top N largest output bundles/chunks (raw, gzip, brotli).
- Dependency graph fan-in/fan-out for largest chunks.
- Duplicate module/version report.
- Startup-critical vs lazy-load candidate mapping.

### B. Repeated Render Passes

Identify unnecessary render work at component/view-model boundaries:

- Components with unstable props causing avoidable rerenders.
- Derived data recalculated every render without memoization.
- Cross-cutting state updates that invalidate broad subtrees.
- Effects that trigger cascaded state updates.
- Repeated rehydration/recomposition work for unchanged inputs.

**Static signals to collect**

- Components with frequent prop object/function recreation.
- Selectors/helpers invoked redundantly per render cycle.
- Known “expensive tree” paths with broad dependency surfaces.
- Areas missing memoization boundaries around heavy transforms.

### C. Redundant Runtime Projection Steps

Identify repeated data transformation/projection work:

- The same model-to-view projection implemented across multiple call sites.
- Multi-step serialization/deserialization performed repeatedly in a request/render lifecycle.
- Conversion pipelines that allocate intermediate structures unnecessarily.
- Projection helpers that do not cache stable inputs.

**Static signals to collect**

- Projection pipeline inventory (input → intermediate → output).
- Duplicate transformation helper map by semantic equivalence.
- Serialization path map (UI state, network payloads, persistence payloads).
- Hot loop/object allocation suspects from code inspection.

---

## 2) Measurement Plan (for Later Code Mode) + Acceptable Thresholds

> Note: Measurements are to be executed in a later implementation phase. This section defines what to measure and pass/fail thresholds.

### A. Build/Weight Metrics

Measure:

- Total JS shipped on initial load (raw/gzip/brotli).
- Largest 5 chunks size and composition.
- Parse + compile + execute time for initial scripts.
- Unused/duplicated module weight.

Thresholds (target for optimization phase):

- **No regression rule:** Initial JS gzip must not increase by more than **+1%** from baseline.
- **Improvement target:** Reduce initial JS gzip by **10–20%** in prioritized areas.
- **Chunk guardrail:** No new chunk over baseline largest chunk by more than **+5%** unless justified in RFC.

### B. Runtime/Interaction Metrics

Measure:

- Time-to-interactive-related timings (framework-appropriate equivalent).
- Main-thread long tasks during startup and key interactions.
- Render commit duration and render count for hotspot flows.
- Interaction latency for top user journeys.

Thresholds:

- **No regression rule:** p95 interaction latency must remain within **±5%** of baseline at minimum.
- **Improvement target:** p95 interaction latency reduced by **15%** for selected hotspots.
- **Render efficiency target:** Reduce redundant rerender count by **25%** on audited screens.

### C. Projection/Serialization Metrics

Measure:

- End-to-end time spent in projection helpers for representative flows.
- Allocation count/bytes for transformation pipelines.
- Serialization/deserialization CPU cost and invocation frequency.

Thresholds:

- **No regression rule:** CPU time in critical projection path does not increase over baseline.
- **Improvement target:** Reduce projection+serialization CPU time by **20%** on top 3 hotspots.
- **Allocation target:** Reduce intermediate object allocations by **20%** in audited pathways.

### D. Measurement Hygiene

- Use fixed datasets and deterministic scenario scripts.
- Run each benchmark in multiple iterations; report median + p95.
- Capture environment metadata (machine profile, runtime, commit SHA).
- Store baseline and post-change results side-by-side for review.

---

## 3) Risk Controls (Prevent Core Logic Regressions)

### A. Functional Safety Nets

- Preserve/extend unit tests for all optimized codepaths.
- Add golden snapshot tests for projection/serialization outputs.
- Add contract tests for public helper behavior and edge-case handling.
- Require unchanged output semantics before and after refactors.

### B. Change Isolation

- Optimize behind feature flags or scoped toggles where feasible.
- Prefer small, reviewable patches with explicit rollback paths.
- Separate “pure consolidation” commits from “behavior-affecting” commits.

### C. Verification Gates

- CI must pass all existing logic tests before perf tests are considered.
- Add targeted regression suites for modified hotspots.
- Require benchmark evidence for any claim of performance improvement.
- Reject optimizations that improve speed but break determinism/consistency.

### D. Operational Guardrails

- Maintain a performance budget file/check in CI for bundle and runtime limits.
- Document assumptions (input stability, cache invalidation rules, ordering semantics).
- Track risk level per backlog item (Low/Medium/High) with owner sign-off.

---

## 4) Consolidation Candidates (Helpers + Serialization Paths)

### A. Duplicate Helper Consolidation Candidates

- Multiple “normalize/shape” helpers producing equivalent output schemas.
- Repeated date/time/number formatting adapters in separate modules.
- Parallel collection utility implementations (filter-map-group pipelines).
- Near-identical selector/projection helpers diverging only by naming.

### B. Serialization Path Consolidation Candidates

- Separate JSON encoding pipelines for similar payload classes.
- Repeated validation + defaulting logic at API boundary and internal boundary.
- Multiple key-mapping implementations (camelCase/snake_case transforms).
- Duplicated persistence marshaling code across storage adapters.

### C. Consolidation Strategy

- Build canonical helper modules with explicit contracts and type-safe signatures.
- Replace duplicate call sites incrementally with compatibility shims where needed.
- Add invariance tests to ensure old vs new paths are semantically identical.
- Remove dead code only after migration coverage reaches agreed threshold.

---

## 5) Deliverable: Optimization Backlog (Ranked by Impact vs Risk)

Use a 2-axis ranking:

- **Impact:** expected win on weight/speed/user latency.
- **Risk:** chance of logic regression or rollout instability.

### Ranking Rubric

- **High Impact / Low Risk** → do first.
- **High Impact / Medium Risk** → do second with added guardrails.
- **Medium Impact / Low Risk** → batch as parallel cleanup.
- **High Risk** items require design review and phased rollout.

### Backlog Template (to populate after measurement)

| Rank | Item | Category | Expected Impact | Risk | Evidence Needed | Owner | Status |
|---|---|---|---|---|---|---|---|
| 1 | Consolidate duplicate projection helper family A/B | Projection | High | Low | Benchmark + golden parity tests | TBD | Planned |
| 2 | Split oversized startup chunk into lazy feature boundaries | Asset Weight | High | Medium | Bundle diff + interaction timing | TBD | Planned |
| 3 | Memoize expensive derived selector on key screens | Render Pass | Medium | Low | Rerender counts + p95 latency | TBD | Planned |
| 4 | Unify serialization pipeline for payload type X | Serialization | Medium | Medium | CPU profile + contract tests | TBD | Planned |
| 5 | Replace duplicate utility lib usage with shared lightweight helpers | Asset Weight | Medium | Low | Dependency diff + bundle report | TBD | Planned |

### Definition of Done for the Deliverable

- Backlog includes at least top 10 ranked items.
- Every item includes baseline evidence and expected KPI delta.
- Every medium/high-risk item includes explicit regression controls.
- Approved by engineering owner(s) for execution sequencing.

---

## Execution Notes

- This document is planning-only and intentionally tool-agnostic.
- Concrete measurement scripts, exact commands, and benchmark outputs will be added during Code mode execution.
