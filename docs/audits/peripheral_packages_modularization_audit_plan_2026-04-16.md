# Peripheral Packages Modularization Audit Plan

Date: 2026-04-16

## 1) Scope

Primary implementation scope:

- `MyCiteV2/packages/modules/cross_domain/**`

Related architecture scope (ports/adapters that consume or expose cross-domain behavior):

- `MyCiteV2/packages/ports/**`
- `MyCiteV2/packages/adapters/**`
- `MyCiteV2/packages/modules/**` (only modules that call into `cross_domain`)

Out-of-scope for direct refactor in this pass (but in-scope for impact analysis):

- UI-only presentation changes not required for modular extraction
- Deployment packaging changes unless a contract test demonstrates a necessary adjustment

### Audit inventory pass

For each peripheral module under `cross_domain`, inventory:

1. Public entrypoints (functions/classes/constants exposed outside the module)
2. Inbound dependencies (who calls it)
3. Outbound dependencies (what ports/adapters/services it calls)
4. Side effects (filesystem/network/process/env/global state)
5. Contract-relevant inputs/outputs (schemas, identifiers, error codes)

Deliverable: one module matrix capturing current coupling posture and extraction risk level (`low`, `medium`, `high`).

## 2) Port/Adapter Conformance Checks per Peripheral Module

Use the following conformance checklist module-by-module.

### A. Directionality checks (Hexagonal boundaries)

- Module depends on `ports` interfaces, not concrete `adapters`, for infrastructure concerns.
- Any adapter-specific import inside `cross_domain` is flagged and replaced with a port abstraction.
- Adapters import module contracts; modules do not import adapter internals.

### B. API surface checks

- Peripheral module exposes a stable, minimal public API (`__all__`/documented exports).
- Input validation and normalization happen at boundary functions (not scattered internally).
- Output types/shape match the port contract and remain deterministic.

### C. Error and observability checks

- Domain-significant failures map to explicit error codes/messages used by existing contracts.
- Logging/telemetry keys are consistent and non-adapter-specific.
- No swallowed exceptions that hide contract violations.

### D. State and side-effect checks

- Pure transform logic remains side-effect-free and testable in isolation.
- Side effects (I/O, store writes, external process calls) are mediated through ports.
- Cache/memoization behavior is explicit and resettable in tests.

### E. Backward-compatibility checks

- Existing aliases/legacy field names are consumed only in compatibility adapters or dedicated compatibility layers.
- Canonical outward naming is preserved from modules through ports/adapters to tests.

## 3) Shared Utility Extraction Opportunities (Remove Repeated Patterns)

During the audit, identify repeated logic across peripheral modules and classify into extraction candidates.

### Candidate categories

- Identifier normalization/parsing utilities
- Canonical/legacy alias mapping helpers
- Error code factories and structured exception wrappers
- Contract payload shaping/merging helpers
- Path/key composition helpers for datum-store interactions
- Common guard clauses (null/empty/default handling)

### Extraction rules

- Extract only when repeated in 2+ modules and semantics are truly shared.
- Prefer placing shared utilities in a neutral package (e.g., `packages/modules/shared` or `packages/ports/...` where appropriate), avoiding new cyclic imports.
- Keep compatibility-only helpers separate from canonical utility modules.
- Preserve behavior with characterization tests before and after extraction.

### Anti-patterns to eliminate

- Copy-pasted normalization snippets with subtle divergence
- Module-local constants duplicating canonical vocabulary values
- Adapter error formatting leaking into domain/peripheral modules

## 4) Contract Integrity Checks Using Existing Tests

Primary verification suites:

- `MyCiteV2/tests/contracts/`
- `MyCiteV2/tests/adapters/`

### Integrity gate

For each phase, require:

1. Contract tests pass with no newly introduced skips.
2. Adapter tests pass for all touched adapter families.
3. No contract snapshot/schema drift unless explicitly planned and documented.

### Recommended execution posture

- Run focused tests first for touched modules/adapters.
- Run full `contracts` and `adapters` suites before merge.
- If failures surface, classify as:
  - pre-existing unrelated
  - extraction regression
  - contract clarification required

### Additional safeguards

- Add characterization tests around currently implicit behaviors before moving shared logic.
- Where behavior is ambiguous, codify expected behavior in contract tests first, then refactor.

## 5) Migration Guidance: Phased Extraction Without Breaking One-Shell Behavior

Adopt a phased rollout that preserves one-shell runtime behavior at every step.

### Phase 0 — Baseline & freeze

- Capture baseline contract/adapter results.
- Freeze canonical one-shell contract assumptions used by peripheral modules.

### Phase 1 — Non-invasive preparation

- Add module inventory matrix and conformance findings.
- Introduce shared helper modules with no call-site switches yet (or behind compatibility wrappers).

### Phase 2 — Incremental extraction

- Migrate one repeated pattern family at a time.
- Keep old call paths as thin delegates where needed to reduce merge risk.
- Avoid cross-cutting changes across many modules in a single commit.

### Phase 3 — Port tightening

- Remove direct adapter dependencies from `cross_domain` modules.
- Route all side effects through explicit ports.
- Ensure adapter bindings remain backward-compatible.

### Phase 4 — Compatibility pruning (only when green)

- Remove redundant compatibility shims once tests confirm no consumers depend on them.
- Retain explicit deprecation notes for any planned removal window.

### Phase 5 — Finalization

- Re-run full contract and adapter suites.
- Publish an audit summary of extracted utilities, conformance outcomes, and remaining debt.

## Exit Criteria

- Every audited peripheral module has a completed conformance checklist.
- Repeated patterns moved to shared utilities where justified, with test coverage.
- `tests/contracts` and `tests/adapters` are green after final extraction phase.
- One-shell behavior remains unchanged from the baseline from the perspective of contract tests and adapter integration tests.
