# Desktop Access and Historical Drift Audit Plan

Date: 2026-04-16

## 1) Desktop usage/support requirements and modular boundary expectations

### Desktop posture requirements

- Preserve a **single-shell mental model** (`/portal/system`) while allowing desktop packaging as a distribution channel, not as a parallel product.
- Ensure desktop launches honor the same canonical navigation, runtime envelope, and tool mediation rules as web.
- Maintain deterministic startup: one bootstrap sequence, one workspace selection contract, one runtime authority.
- Support offline-tolerant read/write behavior only where existing contracts already permit local-first durability.
- Enforce platform-agnostic behavior expectations across macOS, Windows, and Linux for file paths, process invocation, and shell adapters.

### Modular boundary expectations

- Keep `SYSTEM` workspace behavior reducer-owned where already canonical; desktop adapter code must not mutate canonical runtime semantics.
- Constrain desktop-specific logic to adapter/host boundaries (windowing, native menus, process lifecycle, filesystem affordances).
- Keep tool contracts domain-first (`tool_id`, document id, route/query projection) and avoid host-specific branching in core logic.
- Require boundary tests that prove identical behavior for the same command/query inputs independent of host (web vs desktop runtime).
- Treat native APIs as optional capabilities surfaced through explicit ports, never direct imports from core domain modules.

## 2) Compatibility inventory for shell/runtime assumptions that block desktop posture

### High-risk assumptions to inventory

- **Path assumptions**
  - hard-coded POSIX separators (`/`) vs cross-platform `pathlib`/normalized path APIs
  - assumptions that writable runtime paths always exist under deployed folder layouts
- **Process/shell assumptions**
  - dependence on one shell family or one CLI quoting model
  - reliance on interactive TTY behavior where headless/non-interactive execution may be required
- **URL/route assumptions**
  - implicit browser-only deep-link handling
  - route persistence coupled to web-only query semantics without desktop startup translation
- **Storage assumptions**
  - direct writes to repo-relative paths instead of capability-routed datum-store adapters
  - concurrency assumptions that ignore desktop multi-window/session scenarios
- **UI shell assumptions**
  - layout/container code expecting browser viewport primitives only
  - keyboard shortcut handling conflicts between web and native menu accelerators

### Inventory output format (recommended)

For each finding, record:

- module/file
- assumption category (path/process/url/storage/ui)
- current behavior
- desktop impact/severity (critical/high/medium/low)
- proposed remediation boundary (core/adapter/config/test)
- owner and target phase

## 3) Historical drift audit method: compare legacy behavior intent vs current one-shell paradigm

### Method

1. **Define canonical target contract**
   - Use current one-shell principles as the target truth: one shell, one reducer-owned workspace authority, one runtime-owned projection model.
2. **Capture legacy intent artifacts**
   - Collect prior release docs, contract tests, route conventions, and deprecated aliases that represented user-visible intent.
3. **Build intent-vs-current matrix**
   - For each behavior, map:
     - legacy intent statement
     - current implementation outcome
     - drift class (`intent preserved`, `intent narrowed`, `intent broken`, `intent obsolete`)
4. **Validate with executable evidence**
   - Back each matrix row with tests, fixtures, or reproducible traces (not narrative-only judgment).
5. **Decide reconciliation action**
   - `keep as-is`, `restore behavior`, `provide compatibility shim`, or `retire with migration note`.

### Drift classes and decision rubric

- **Intent preserved**: keep; optionally improve naming/docs.
- **Intent narrowed**: restore if contractual; otherwise document intentional simplification.
- **Intent broken**: prioritize fix or compatibility shim.
- **Intent obsolete**: deprecate formally, define sunset timeline, and provide migration cues.

## 4) Reimplementation candidate list for contractual behaviors worth carrying forward

### Candidate behaviors

- Canonical deep-link restoration into `SYSTEM` workspace context with deterministic startup focus.
- Stable tool identity and alias intake where legacy IDs are still contractual (compatibility-only, warning-instrumented).
- Canonical datum/document ID mapping behavior for persisted workspace artifacts.
- Explicit back-out/focus contraction rules (`sandbox -> file -> datum -> object`) where users depend on navigation predictability.
- Runtime-owned projection of route/query state for reducer-owned surfaces.
- Read-only service adapters for legacy data footprints that must remain queryable during phased migration.

### Candidate acceptance criteria

- Behavior can be expressed as an explicit contract test.
- Behavior is user-visible and historically relied upon.
- Reimplementation does not introduce a second shell/state authority.
- Added complexity is bounded to adapter/compat layers and can be sunset.

## 5) Deliverable: phased reconciliation plan preserving simplicity/unification goals

## Phase 0 — Discovery and inventory (1 sprint)

- Produce compatibility inventory with severity ranking.
- Complete historical intent-vs-current matrix for top user-visible flows.
- Identify no-go items that would violate one-shell authority model.

## Phase 1 — Critical contract reconciliation (1–2 sprints)

- Reimplement critical contractual behaviors via thin compatibility modules.
- Add/expand contract tests in runtime, adapter, and integration layers.
- Add warning/telemetry codes for legacy path usage.

## Phase 2 — Desktop adapter hardening (1 sprint)

- Normalize path/process handling across platforms.
- Implement startup/deep-link translation into canonical one-shell state.
- Validate keyboard/menu and lifecycle behavior parity.

## Phase 3 — Simplification guardrails and deprecation (ongoing)

- Remove temporary shims that are no longer contractually required.
- Publish deprecation timelines and migration notes.
- Keep a single canonical architecture statement and reject reintroducing parallel shell models.

### Exit criteria

- All critical/high findings resolved or accepted with explicit waivers.
- Contract test suite demonstrates parity for agreed historical behaviors.
- Desktop and web variants share one canonical state/routing authority.
- Remaining compatibility paths have owners, sunset dates, and telemetry.
