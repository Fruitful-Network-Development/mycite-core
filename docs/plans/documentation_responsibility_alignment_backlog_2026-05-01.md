# Documentation Responsibility Alignment Backlog

Date: 2026-05-01

Doc type: `plan`
Normativity: `supporting`
Lifecycle: `active`
Last reviewed: `2026-05-01`

## Purpose

Track the lossless documentation alignment work that clarifies separation,
responsibility, promotion targets, and deferred peripheral follow-ons.

## Scope

- `docs/README.md`
- `docs/contracts/README.md`
- `docs/wiki/*`
- `docs/personal_notes/README.md`
- cross-repo ownership articulation that connects `mycite-core`, `srv-infra`,
  `/srv/webapps`, and `/srv/mycite-state`

## Canonical Contract Links

- portal shell contract: `docs/contracts/portal_shell_contract.md`
- route model: `docs/contracts/route_model.md`
- surface catalog: `docs/contracts/surface_catalog.md`
- vocabulary glossary: `docs/contracts/portal_vocabulary_glossary.md`
- tool operating contract: `docs/contracts/tool_operating_contract.md`

## Task Mapping

- `TASK-DOC-RESP-ALIGN-001`: strengthen doc-family indexes and cross-repo responsibility maps
- `TASK-DOC-RESP-ALIGN-002`: define personal-note promotion targets and extraction rules
- `TASK-DOC-RESP-ALIGN-003`: track FND-EBI peripheral split as deferred follow-on work
- `TASK-DOC-RESP-ALIGN-004`: track portal host capability bootstrap clarification as deferred follow-on work

## Backlog

1. `TASK-DOC-RESP-ALIGN-001`
   - Preserve the corpus and improve how readers locate current truth versus
     plans, evidence, and notes.

2. `TASK-DOC-RESP-ALIGN-002`
   - Treat personal notes as preserved source material, not as silent canon.
   - Promote reproducible content into wiki, contract, plan, or audit surfaces.

3. `TASK-DOC-RESP-ALIGN-003`
   - FND-EBI peripheral split:
     separate hosted profile registry and analytics visibility expectations more
     explicitly in documentation and contracts before broadening the surface.
   - Deferred agentic task:
     `FND-EBI-Peripheral-Split-2026-05-01`

4. `TASK-DOC-RESP-ALIGN-004`
   - Portal host capability bootstrap:
     replace instance-id special-casing with authority-backed capability policy
     and document the boundary clearly.
   - Deferred agentic task:
     `Portal-Host-Capability-Bootstrap-2026-05-01`

## Rationale

The corpus already contains most of the needed material. The gap is assignment:

- which docs are canonical
- which docs are explanatory
- which docs are evidence
- which notes are preserved source material awaiting promotion

This backlog keeps that alignment work explicit without deleting history.

## Exit Criteria

- Repo indexes point to the correct doc families.
- Personal notes have explicit promotion targets.
- Deferred peripheral/boundary work is recorded as named follow-on tasks.
