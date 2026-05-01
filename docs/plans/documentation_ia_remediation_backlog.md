# Documentation IA Remediation Backlog

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-22`

## Purpose

Track and prioritize remediation work from the documentation + agent-yaml optimization audit.

## Scope

Active documentation under `docs/audits` and `docs/plans`, and guided agent YAML standards under `docs/standards`.

## Status Note — 2026-05-01

The 2026-05-01 responsibility-alignment pass keeps this file as the broad doc-IA
backlog, but moves the lossless separation/responsibility follow-on work into:

- `docs/plans/documentation_responsibility_alignment_backlog_2026-05-01.md`

That newer backlog is the canonical pointer for:

- repo-family orientation improvements
- personal-note promotion targets
- deferred FND-EBI documentation/peripheral split work
- deferred portal host capability bootstrap clarification

## Status Note — 2026-04-22

The MOS final cut-over pass updated the active plan/audit/contract/runtime documentation
set to describe SQL-backed authority for migrated `SYSTEM` surfaces, added the final MOS
closure reports, reviewed the closure-time `31`-artifact corpus in `docs/plans/` plus
`docs/audits/reports/`, and published
`docs/audits/reports/mos_program_closure_audit_checklist_2026-04-21.md` to classify
active versus historical evidence explicitly.

Current repo state:

- lifecycle metadata headers are now present across the active plan/audit set
- the remaining doc-IA backlog is concentrated in contract-link coverage for older active
  plan docs, rationale/terminology cleanup, and YAML/CI enforcement

## Completed In Current Repo State

1. **Lifecycle Metadata Retrofit**
   - Explicit doc type/normativity/lifecycle/last-reviewed headers are now present on the
     active plan and audit files.
   - Remaining backlog should no longer treat metadata headers as open work.

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`

## Prioritized Remaining Backlog

1. **P1 - Contract Link Coverage Expansion**
   - Ensure the remaining active plan docs that still predate the contract-link retrofit
     gain a `Canonical Contract Links` section.
   - Risk reduced: contract drift and reader ambiguity.

2. **P2 - Rationale Gap Closure**
   - Add `Rationale` sections where normative claims currently have no design explanation.
   - Risk reduced: future rework from missing trade-off context.

3. **P2 - Terminology Drift Sweep**
   - Replace stale terms with canonical glossary terms or mark as compatibility aliases.
   - Risk reduced: implementation and review confusion.

4. **P2 - YAML Task Adoption and Validation Expansion**
   - Require new guided-task YAML artifacts to follow `docs/standards/agent_yaml_schema.md`
     and expand validation coverage for standards/doc linkage presence where practical.
   - Risk reduced: non-deterministic execution and weak traceability.

5. **P2 - Responsibility-Family Orientation**
   - Keep `documentation_ia_remediation_backlog.md` as the broad IA backlog and use
     `documentation_responsibility_alignment_backlog_2026-05-01.md` for the focused
     separation/responsibility stream.
   - Risk reduced: duplicated backlog intent and weak doc-family assignment.

## Exit Criteria

- Active plan/audit docs have contract link blocks.
- Active plan/audit docs have lifecycle metadata.
- New guided tasks use the standard YAML schema and templates.
- Validation checks exist for standards/doc linkage presence.
