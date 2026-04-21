# Documentation IA Remediation Backlog

Doc type: `plan`  
Normativity: `supporting`  
Lifecycle: `active`  
Last reviewed: `2026-04-21`

## Purpose

Track and prioritize remediation work from the documentation + agent-yaml optimization audit.

## Scope

Active documentation under `docs/audits` and `docs/plans`, and guided agent YAML standards under `docs/standards`.

## Status Note — 2026-04-21

The MOS final cut-over pass updated the active plan/audit/contract/runtime documentation set to describe SQL-backed authority for migrated `SYSTEM` surfaces, added the final MOS closure reports, reviewed the closure-time `31`-artifact corpus in `docs/plans/` plus `docs/audits/reports/`, and published `docs/audits/reports/mos_program_closure_audit_checklist_2026-04-21.md` to classify active versus historical evidence explicitly.

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`

## Prioritized Backlog

1. **P1 - Contract Link Coverage Expansion**
   - Ensure all active audits/plans include a `Canonical Contract Links` section.
   - Risk reduced: contract drift and reader ambiguity.

2. **P1 - Lifecycle Metadata Retrofit**
   - Add explicit doc type/normativity/lifecycle/last-reviewed headers to active plan and audit files.
   - Risk reduced: stale interpretation and misuse of historical docs.

3. **P2 - Rationale Gap Closure**
   - Add `Rationale` sections where normative claims currently have no design explanation.
   - Risk reduced: future rework from missing trade-off context.

4. **P2 - Terminology Drift Sweep**
   - Replace stale terms with canonical glossary terms or mark as compatibility aliases.
   - Risk reduced: implementation and review confusion.

5. **P2 - YAML Task Adoption**
   - Require new guided-task YAML artifacts to follow `docs/standards/agent_yaml_schema.md`.
   - Risk reduced: non-deterministic execution and weak traceability.

## Exit Criteria

- Active plan/audit docs have contract link blocks.
- Active plan/audit docs have lifecycle metadata.
- New guided tasks use the standard YAML schema and templates.
- Validation checks exist for standards/doc linkage presence.
