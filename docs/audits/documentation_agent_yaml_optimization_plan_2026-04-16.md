# Documentation + Agent YAML Optimization Plan (2026-04-16)

## Purpose

Define a repeatable documentation information-architecture (IA) and agent-YAML optimization program so planning, implementation, and audit artifacts remain:

- canonically aligned with portal contracts,
- decomposable into independently verifiable agent tasks,
- and auditable through explicit evidence trails.

---

## 1) Documentation IA Audit Scope (`docs/`)

### 1.1 Audit objectives

Perform an IA audit across all documentation under `docs/` with focus on:

1. **Redundancy**: duplicated requirements, repeated terminology maps, and duplicate process guidance across `README`, `plans`, `audits`, and `contracts`.
2. **Stale terminology**: references to deprecated shell/surface language, legacy aliases that should be compatibility-only, and outdated version-target statements.
3. **Missing design rationale**: normative requirements without an explicit “why”, including unresolved trade-offs and missing compatibility rationale.

### 1.2 Inventory + classification model

For each document, classify by:

- **Doc type**: `contract`, `audit`, `plan`, `notes`.
- **Normativity**: `canonical`, `supporting`, `historical`.
- **Lifecycle status**: `active`, `compatibility`, `deprecated`, `archived`.
- **Source of truth link**: canonical contract file and section.

### 1.3 IA audit checklist

For each file in `docs/`:

- Confirm header includes purpose and scope.
- Confirm contract dependencies are explicitly linked.
- Flag repeated requirement text better represented as links to canonical contracts.
- Flag stale terms and map to canonical vocabulary.
- Confirm rationale section exists for each major normative decision.
- Confirm date/version context is explicit and non-ambiguous.

### 1.4 IA audit deliverables

- **Redundancy report**: duplicate content matrix with keep/remove/merge action.
- **Terminology drift report**: stale → canonical term map and remediation targets.
- **Rationale gap list**: requirement statements lacking design rationale.
- **Remediation backlog**: prioritized tasks by risk (`contract drift`, `implementation risk`, `reader confusion`).

---

## 2) YAML Spec Audit for Agent Task Decomposition

### 2.1 Audit objective

Standardize agent task YAML so every task is machine-parseable and reviewable for:

- clear ownership,
- deterministic dependency order,
- explicit outputs,
- and enforceable validation gates.

### 2.2 Decomposition dimensions

Every task spec must encode:

- **Ownership**
  - `owner.role` (e.g., `doc-author`, `contract-maintainer`, `qa-auditor`)
  - `owner.team` (if applicable)
  - `review.required_by` (who can approve)
- **Dependencies**
  - hard dependencies (must complete before task starts)
  - soft dependencies (informational but non-blocking)
  - cross-doc dependencies (contract sections, prior audit outputs)
- **Outputs**
  - target files and sections
  - expected artifact type (`markdown`, `yaml`, `json`, `screenshot`, `log`)
  - evidence paths and acceptance evidence IDs
- **Validation gates**
  - schema validation
  - contract-link validation
  - acceptance-criteria validation
  - evidence-path existence checks

### 2.3 YAML audit checks

1. No missing owner metadata.
2. No circular hard dependencies.
3. Every output has explicit path and artifact type.
4. Every acceptance criterion is testable and mapped to evidence.
5. Every canonical claim links to a contract document reference.
6. Validation gates are executable without manual interpretation.

### 2.4 YAML audit deliverables

- schema conformance report,
- dependency graph report,
- orphan-output report (outputs not referenced by acceptance criteria),
- gate coverage report (criteria without validation gates).

---

## 3) Required Templates for Guided Agent Tasks

## 3.1 Template A — Task Metadata (required)

```yaml
task:
  id: DOC-AUDIT-000
  title: "<concise action + object>"
  summary: "<one-sentence objective>"
  owner:
    role: "doc-author"
    team: "<team-or-null>"
  status: "planned"
  priority: "p2"
  tags: ["docs", "contracts", "audit"]
  relates_to:
    contracts:
      - doc: "docs/contracts/portal_shell_contract.md"
        section: "<section-title-or-anchor>"
  dependencies:
    hard: []
    soft: []
  inputs:
    - path: "docs/audits/<input>.md"
      type: "markdown"
  outputs:
    - path: "docs/audits/<output>.md"
      type: "markdown"
```

## 3.2 Template B — Acceptance Criteria (required)

```yaml
acceptance:
  criteria:
    - id: AC-1
      statement: "All normative terms align with canonical glossary terms."
      validation:
        gate: "terminology_alignment"
        method: "link_and_term_scan"
      evidence:
        - id: EV-AC-1
          path: "docs/audits/evidence/EV-AC-1.md"
```

## 3.3 Template C — Evidence Path Contract (required)

```yaml
evidence:
  root: "docs/audits/evidence"
  artifacts:
    - id: EV-1
      path: "docs/audits/evidence/<task-id>/summary.md"
      type: "markdown"
      producer: "agent"
      immutable: true
    - id: EV-2
      path: "docs/audits/evidence/<task-id>/validation.log"
      type: "log"
      producer: "validator"
      immutable: true
```

### 3.4 Template policy requirements

- `task.id` must be globally unique.
- `acceptance.criteria[].id` must be unique within a task.
- Every criterion must include at least one evidence artifact.
- Evidence paths must be repository-relative, stable, and non-temp.
- Required template blocks are mandatory; optional extensions may be added under `extensions`.

---

## 4) Cross-link Requirements to Canonical Contracts

Every non-trivial docs/audit/plan artifact must include a **Canonical Contract Links** section containing direct references to:

- `docs/contracts/portal_shell_contract.md`
- `docs/contracts/route_model.md`
- `docs/contracts/surface_catalog.md`
- `docs/contracts/portal_vocabulary_glossary.md`

### 4.1 Link rule set

1. Normative claims (`must`, `canonical`, `required`) require at least one contract link.
2. If a claim is compatibility-only, link glossary + relevant contract section and mark lifecycle as `compatibility`.
3. If no contract reference exists, mark the claim as `proposed` and open a contract update task.
4. Plans and audits must not silently redefine contract semantics.

### 4.2 Minimum link block template

```markdown
## Canonical Contract Links
- portal shell contract: `docs/contracts/portal_shell_contract.md` (section: ...)
- route model: `docs/contracts/route_model.md` (section: ...)
- surface catalog: `docs/contracts/surface_catalog.md` (section: ...)
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md` (section: ...)
```

---

## 5) Output

## 5.1 Proposed doc tree updates

```text
docs/
  contracts/
    README.md
    portal_shell_contract.md
    route_model.md
    surface_catalog.md
    portal_vocabulary_glossary.md

  standards/
    documentation_style_guide.md
    agent_yaml_schema.md
    agent_task_template_examples.md

  audits/
    README.md
    documentation_agent_yaml_optimization_plan_2026-04-16.md
    evidence/
      <task-id>/
        summary.md
        validation.log

  plans/
    README.md
    documentation_ia_remediation_backlog.md
```

### 5.2 Standardized agent YAML schema (v1)

```yaml
schema_version: "1.0"
kind: "agent_task"

task:
  id: "<string>"
  title: "<string>"
  summary: "<string>"
  owner:
    role: "<string>"
    team: "<string-or-null>"
  status: "planned|in_progress|blocked|done"
  priority: "p0|p1|p2|p3"
  lifecycle: "active|compatibility|deprecated|archived"
  tags: ["<string>"]

  relates_to:
    contracts:
      - doc: "docs/contracts/<file>.md"
        section: "<section-or-anchor>"

  dependencies:
    hard: ["<task-id>"]
    soft: ["<task-id>"]

  inputs:
    - path: "<repo-relative-path>"
      type: "markdown|yaml|json|log|image"

  outputs:
    - path: "<repo-relative-path>"
      type: "markdown|yaml|json|log|image"
      required: true

acceptance:
  criteria:
    - id: "AC-<n>"
      statement: "<testable assertion>"
      validation:
        gate: "schema|contracts|terminology|evidence|custom"
        method: "<executable-check-or-procedure>"
      evidence_ids: ["EV-<n>"]

evidence:
  root: "docs/audits/evidence"
  artifacts:
    - id: "EV-<n>"
      path: "<repo-relative-path>"
      type: "markdown|yaml|json|log|image"
      producer: "agent|validator|human"
      immutable: true

validation_gates:
  - id: "VG-1"
    name: "schema_validation"
    required: true
  - id: "VG-2"
    name: "contract_link_validation"
    required: true
  - id: "VG-3"
    name: "acceptance_to_evidence_mapping"
    required: true
```

### 5.3 Adoption phases

1. **Phase 1 (baseline)**: add standards docs and templates; require contract links in all new audits/plans.
2. **Phase 2 (migration)**: retrofit active docs with lifecycle metadata and rationale blocks.
3. **Phase 3 (enforcement)**: CI validation for YAML schema, evidence-path existence, and contract-link coverage.
4. **Phase 4 (hardening)**: remove duplicated normative content and retain single-source canonical references.

---

## Success Criteria

- IA audit completed with actioned redundancy/staleness/rationale findings.
- Standardized agent YAML schema accepted and used by new guided tasks.
- Canonical contract links present in all active plans/audits.
- Validation gates enforce acceptance/evidence traceability before task closure.
