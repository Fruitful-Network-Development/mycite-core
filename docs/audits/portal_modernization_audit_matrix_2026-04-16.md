# Portal Modernization Audit Matrix (2026-04-16)

This matrix defines the coordinated audit tracks for portal modernization work, including ownership, scope, dependencies, and standardized outputs.

## Audit Tracks

| Track | Owner Agent | Primary Paths | Inputs | Deliverables | Dependency Tracks | Definition of Done |
|---|---|---|---|---|---|---|
| Shell & Composition | `agent-shell` | `apps/portal/shell/**`, `apps/portal/layout/**`, `docs/contracts/portal_shell_contract.md` | Portal shell contract, current shell implementation, app composition map | Shell audit report, contract variance list, composition boundary recommendations | None | All shell contract clauses mapped to implementation status (met / partial / unmet), with evidence and actionable remediations |
| Route Model & Navigation | `agent-routing` | `apps/portal/routes/**`, `apps/portal/navigation/**`, `docs/contracts/route_model.md` | Route model contract, route registry, navigation manifests | Route conformity findings, dead/ambiguous route list, migration-safe route plan | Shell & Composition | Every route is classified (canonical / deprecated / orphaned), and navigation behavior matches route contract |
| Surface Inventory & Ownership | `agent-surfaces` | `apps/portal/features/**`, `apps/portal/pages/**`, `docs/contracts/surface_catalog.md` | Surface catalog contract, feature ownership map, page/component exports | Surface inventory diff, ownership gaps, rationalization candidates | Route Model & Navigation | All user-facing surfaces are cataloged with owner, route binding, lifecycle state, and modernization priority |
| UX Semantics & Vocabulary | `agent-vocabulary` | `apps/portal/ui/**`, `apps/portal/content/**`, `docs/contracts/portal_vocabulary_glossary.md` | Vocabulary glossary, UX copy inventory, component labels/tokens | Terminology consistency audit, synonym conflict list, copy normalization candidates | Surface Inventory & Ownership | Critical journey terminology is normalized; conflicting terms mapped to approved canonical vocabulary |
| Data Contracts & Integration Seams | `agent-data` | `apps/portal/api/**`, `apps/portal/data/**`, `apps/portal/integrations/**` | API schema docs, DTO/type definitions, integration configs | Contract drift findings, seam risk register, adapter/refactor candidates | Shell & Composition; Route Model & Navigation | Integration points have explicit contract status and modernization-safe seams identified |
| NFR, Security & Observability | `agent-nfr` | `apps/portal/security/**`, `apps/portal/telemetry/**`, `apps/portal/perf/**` | Security baselines, telemetry standards, perf SLOs, incident history | NFR gap audit, control coverage matrix, prioritized hardening backlog | Data Contracts & Integration Seams; Surface Inventory & Ownership | Key NFR controls (authz, auditability, latency, error budgets, logging) are evaluated with measurable gap statements |
| Testability & Release Readiness | `agent-release` | `apps/portal/tests/**`, `apps/portal/e2e/**`, `.github/workflows/**`, `scripts/release/**` | Existing test suite, CI config, release checklist, defect leakage data | Test coverage risk map, CI bottleneck analysis, release gating recommendations | NFR, Security & Observability; UX Semantics & Vocabulary | Modernization scope has explicit quality gates, test strategy updates, and release risk mitigations |

## Sequencing Rules

### Parallelizable at Start
- **Shell & Composition** and **Data Contracts & Integration Seams** may start in parallel when both can independently gather baseline evidence.
- **Route Model & Navigation** may begin in parallel with **Data Contracts & Integration Seams** after the shell baseline snapshot is captured.

### Must Follow Prior Tracks
- **Surface Inventory & Ownership** must run after **Route Model & Navigation** establishes canonical route bindings.
- **UX Semantics & Vocabulary** must run after **Surface Inventory & Ownership** so terminology is tied to confirmed surfaces.
- **NFR, Security & Observability** must run after **Data Contracts & Integration Seams** and **Surface Inventory & Ownership** so control evaluation reflects actual seams/surfaces.
- **Testability & Release Readiness** must run last, after NFR and UX outputs are available, to define final quality and release gates.

### Practical Execution Pattern
1. Start: Shell + Data (parallel)
2. Then: Route
3. Then: Surface
4. Then: UX + NFR (parallel once Surface and Data prerequisites are met)
5. Final: Testability/Release

## Shared Terminology (Contract Sources)

All agents must use consistent terms defined in the following contract references:

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`

### Terminology Usage Requirements
- Prefer canonical contract terms over colloquial aliases in all findings.
- When legacy terms appear in code/evidence, report as: `legacy_term -> canonical_term`.
- If a term is missing from the glossary, mark it as **proposed** and include rationale; do not treat as canonical until approved.
- Cross-track reports must preserve the same entity naming for shell regions, routes, and surfaces.

## Required Output Template (All Agents)

Every audit output must use the template below for consistency.

```md
# <Track Name> Audit Output

## 1) Findings
- **Finding ID**: <TRACK-###>
- **Summary**: <clear statement of what is true>
- **Severity**: <Critical|High|Medium|Low>
- **Scope**: <paths / modules / routes affected>
- **Contract Reference**: <specific section in contract document>

## 2) Risks
- **Risk ID**: <R-###>
- **Linked Findings**: <TRACK-###, ...>
- **Impact**: <user/business/engineering impact>
- **Likelihood**: <High|Medium|Low>
- **Exposure Window**: <current / migration phase / post-cutover>

## 3) Evidence Pointers
- **Code Evidence**: <repo path + line(s) or symbol>
- **Runtime/Telemetry Evidence**: <dashboard/log/query reference>
- **Document Evidence**: <contract/doc section references>
- **Confidence**: <High|Medium|Low> with brief justification

## 4) Remediation Candidates
- **Candidate ID**: <RC-###>
- **Targets**: <finding/risk IDs addressed>
- **Change Type**: <refactor|contract update|deprecation|test|observability|security>
- **Proposed Action**: <concise implementation direction>
- **Dependencies**: <other tracks/teams>
- **Estimated Effort**: <S|M|L>
- **Owner Recommendation**: <team/role>

## 5) Decision Notes (Optional)
- **Open Questions**
- **Assumptions**
- **Out-of-Scope Items**
```

### Output Quality Bar
- Findings must be evidence-backed and contract-linked.
- Risks must map to at least one finding.
- Remediation candidates must be actionable and dependency-aware.
- Avoid narrative-only reports; use structured bullets exactly as above.
