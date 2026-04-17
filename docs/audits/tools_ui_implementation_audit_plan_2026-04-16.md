# Tools UI Implementation Audit Plan (2026-04-16)

## Objective

Produce a reproducible audit that maps every portal tool implementation from static shell/UI code through runtime handler logic, then identifies drift and duplication risks between shell-core behavior and tool-specific renderers.

The final output of this plan is a **mismatch report** with remediation candidates and consolidation points.

---

## Scope

### 1) Static assets and host template

Audit the shell-facing static assets and host template:

- `MyCiteV2/instances/_shared/portal_host/static/*.js`
- `MyCiteV2/instances/_shared/portal_host/templates/portal.html`

Focus areas:

- tool registration and routing wiring
- state bootstrap and hydration inputs
- event/message contracts used by runtime-backed tool surfaces
- renderer invocation sites and renderer selection logic
- shell-level projection/transformation before renderer calls

### 2) Runtime handlers

Audit runtime orchestration and handlers under:

- `MyCiteV2/instances/_shared/runtime/**`

Focus areas:

- tool runtime entry points (handler dispatch, tool resolution, and slug binding)
- per-tool response contracts and state envelope construction
- canonical state projection boundaries (runtime-owned vs shell-owned)
- any runtime-side rendering hints or mode flags that affect UI behavior

---

## Deliverables

## Primary deliverable

`tools_ui_implementation_mismatch_report_2026-04-16.md` (name may be adjusted if repo conventions require), containing:

1. tool-by-tool mapping table (`tool slug -> runtime entry -> state projection -> UI renderer path`)
2. mismatch inventory (contract, behavior, naming, projection, fallback)
3. remediation candidates with effort/risk notes
4. suggested consolidation points for shared logic extraction

## Secondary artifacts (optional but recommended)

- inventory CSV/TSV for mapping validation
- diff notes for duplicated logic blocks with file/line references
- checklist completion matrix for drift detection criteria

---

## Audit method

### Phase A — Inventory and discovery

1. Enumerate all tool slugs visible to the portal shell from static JS and template bootstrap code.
2. Enumerate all runtime tool handlers/dispatch entries from `_shared/runtime`.
3. Normalize naming aliases (e.g., slug variants, legacy IDs, route names) into one comparison list.

### Phase B — End-to-end mapping

For each tool slug, trace and document:

1. **Runtime entry**
   - first runtime dispatch/handler path accepting the slug
   - intermediate adapter/normalization layers
2. **State projection**
   - canonical runtime response/state shape
   - shell projection/translation layer (if any)
   - derived UI state consumed by renderer
3. **UI renderer path**
   - concrete renderer module/function invoked
   - shell-core wrappers/hooks invoked before renderer
   - fallback renderer path when runtime response is absent/partial

### Phase C — Mismatch classification

Record mismatches by category:

- **Contract mismatch**: runtime payload keys or types diverge from UI expectations
- **Projection mismatch**: shell derives state differently than runtime semantics imply
- **Renderer mismatch**: tool slug routed to unexpected/legacy renderer path
- **Mode mismatch**: runtime mode flags produce inconsistent shell behavior
- **Fallback mismatch**: error/loading/empty states implemented differently per tool without intent

### Phase D — Drift and duplication assessment

Run the checklist below to detect duplicate logic and shell/tool drift.

### Phase E — Consolidation recommendation drafting

For each mismatch/duplication cluster:

- propose consolidation target (shell core, shared adapter, runtime contract, shared renderer utility)
- estimate blast radius and migration sequence
- identify low-risk first moves (non-breaking wrappers, compatibility shims, test harness additions)

---

## Tool implementation mapping specification

Create a mapping table with one row per canonical tool slug.

Required columns:

1. `tool_slug`
2. `runtime_entry_path`
3. `runtime_entry_symbol`
4. `state_projection_path`
5. `state_projection_symbol`
6. `ui_renderer_path`
7. `ui_renderer_symbol`
8. `route_or_mount_path`
9. `fallback_renderer_path`
10. `notes`

Guidelines:

- if multiple runtime entries exist, include all and mark one as canonical
- if projection is inline in renderer, mark as `inline_projection` and capture call site
- if shell-core pre-processing is present, include both wrapper and final renderer symbols

---

## Drift detection checklist (shell core vs tool-specific renderers)

For each tool, verify:

1. **Loading semantics parity**
   - identical spinner/skeleton trigger rules
   - consistent stale-data handling while refresh is in-flight

2. **Error semantics parity**
   - consistent error surface region, severity mapping, retry affordance
   - consistent handling of runtime timeout vs empty result

3. **Selection/context semantics parity**
   - same selected entity precedence rules
   - same route/query to state synchronization rules

4. **Projection semantics parity**
   - shared field normalization helpers are reused where expected
   - no tool-specific reinterpretation of canonical enum/status values without justification

5. **Capability gating parity**
   - permission/feature-flag checks use shared shell predicates where appropriate
   - no renderer-only hidden gating logic duplicating runtime authorization intent

6. **Navigation semantics parity**
   - tool-level deep-link behavior follows shell conventions
   - back/forward and refresh preserve equivalent state slices

7. **Empty-state parity**
   - absence-of-data messaging follows shell-wide conventions
   - no contradictory “no data” thresholds across tools for same domain object

8. **Telemetry/instrumentation parity**
   - shared event names and payload schemas used where intended
   - no per-tool renamed duplicates for identical user actions

9. **Utility reuse parity**
   - common formatters/derivers imported from shared locations
   - duplicate helper logic flagged when behavior overlaps shell core

10. **Fallback renderer parity**
    - unknown/unsupported states funnel through common fallback mechanisms
    - divergence documented only when intentional and product-approved

---

## Mismatch report structure

1. **Executive summary**
   - number of tools audited
   - number of mismatches by category
   - top 3 consolidation opportunities

2. **Coverage matrix**
   - all tool slugs with mapped runtime/projection/renderer paths

3. **Detailed findings** (one subsection per tool)
   - observed implementation path
   - expected canonical pattern
   - mismatch details
   - risk assessment
   - remediation candidate

4. **Consolidation plan**
   - shared abstractions to introduce
   - candidate modules/functions to deprecate
   - phased rollout sequence

5. **Appendix**
   - file/line references
   - alias normalization map
   - unresolved questions

---

## Suggested remediation/consolidation heuristics

Prioritize candidates that:

1. eliminate duplicated projection logic across 3+ tools
2. centralize loading/error/fallback behavior in shell-core utilities
3. preserve runtime contracts while moving renderer-specific normalization into shared adapters
4. reduce alias/slug translation layers to one canonical mapping boundary
5. add contract tests at runtime->projection and projection->renderer boundaries

---

## Exit criteria

The audit is complete when:

1. every discovered tool slug has a full end-to-end mapping row
2. every mismatch has an owner candidate and remediation direction
3. duplicate shell/tool logic clusters are identified with specific consolidation targets
4. mismatch report is publishable and actionable for implementation planning
