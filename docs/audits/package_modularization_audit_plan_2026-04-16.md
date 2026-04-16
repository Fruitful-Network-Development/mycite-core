# Package Modularization Audit Plan

Date: 2026-04-16

## Scope

This audit is constrained to the following repository areas:

- `MyCiteV2/packages/**`
- `MyCiteV2/instances/_shared/runtime/**`

Out-of-scope code may be referenced only as dependency context when validating boundaries.

## Boundary Checks

### 1) Contract-first imports

Validate that package interactions are routed through declared contracts/interfaces before concrete implementations.

Checks:

- Detect direct imports of concrete internals across package boundaries where contract modules exist.
- Flag bypasses of published package entrypoints in favor of deep internal paths.
- Confirm runtime-layer imports target package contracts and not implementation-only modules.

### 2) Forbidden dependency enforcement

Enforce dependency direction and deny explicit forbidden edges.

Checks:

- Evaluate imports against approved dependency rules (allow-list + deny-list).
- Identify reverse dependencies that violate intended layering.
- Detect cycles that cross domain boundaries or collapse abstraction layers.

### 3) Domain leakage detection

Ensure domains remain encapsulated and do not expose internal state or semantics unintentionally.

Checks:

- Find cross-domain imports that pull domain-specific models/services without a domain contract.
- Identify leakage of domain-only constants, configuration, or persistence details into runtime orchestration paths.
- Flag mixed-responsibility modules that combine unrelated domain concerns.

## Inventory Outputs

Produce the following outputs for the scoped areas:

1. **Current module dependency map**
   - Directed import graph at module and package levels.
   - Boundary-violation annotations on graph edges.

2. **Candidate split/merge proposals**
   - Split candidates for oversized or mixed-responsibility modules.
   - Merge candidates for fragmented modules with tightly coupled lifecycles.
   - Rationale tied to dependency clarity, testability, and ownership boundaries.

3. **Anti-pattern list**
   - Deep-import coupling.
   - Runtime-to-domain implementation reach-through.
   - Bidirectional package dependencies.
   - God modules / utility dumping.
   - Contract drift between interface and implementation usage.

## Required Evidence Pointers

All findings and recommendations must include verifiable evidence pointers to architecture tests under:

- `MyCiteV2/tests/architecture/`

Evidence references should include:

- Test file path(s).
- Relevant rule/test case identifiers.
- Result status (pass/fail) and timestamp/date of execution.

## Remediation Scoring Rubric

Use a weighted tri-axis score per finding/proposal:

- **Impact (1-5)**: architectural risk reduction and maintainability gain.
- **Migration Cost (1-5)**: estimated engineering effort and coordination required.
- **Blast Radius (1-5)**: scope of affected modules, packages, and runtime surfaces.

Recommended prioritization formula:

- `Priority Score = (Impact × 2) + Blast Radius - Migration Cost`

Interpretation:

- **High priority**: high impact, manageable cost, acceptable/contained blast radius.
- **Medium priority**: meaningful gain with moderate migration tradeoffs.
- **Low priority**: low impact or disproportionately high migration cost.

Each remediation item should record all three dimensions plus computed priority score.
