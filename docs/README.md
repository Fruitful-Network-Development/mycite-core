# MyCite V2 Portal Docs

## Start Here

This repository describes one portal shell and one application authority model.

- Canonical public entry: `/portal` -> `/portal/system`
- Canonical shell endpoint: `/portal/api/v2/shell`
- Canonical tool work pages: `/portal/system/tools/<tool_slug>`
- SQL-backed authority is the expected posture for migrated `SYSTEM` surfaces

If you are orienting to repo responsibility first, read:

1. [`docs/wiki/separation_and_responsibility.md`](wiki/separation_and_responsibility.md)
2. [`docs/contracts/README.md`](contracts/README.md)
3. [`docs/plans/README.md`](plans/README.md)

## Documentation Families

This repo uses multiple documentation families on purpose:

- code-adjacent package docs:
  `MyCiteV2/**/README.md`, `module_contract.md`, `allowed_dependencies.md`,
  `forbidden_dependencies.md`, `testing_strategy.md`
- canonical cross-cutting contracts:
  [`docs/contracts/`](contracts/)
- explanatory orientation and responsibility maps:
  [`docs/wiki/`](wiki/)
- execution plans and backlog streams:
  [`docs/plans/`](plans/)
- audits, reports, and evidence:
  [`docs/audits/`](audits/)
- preserved non-canonical idea material:
  [`docs/personal_notes/`](personal_notes/)
- standards and authoring rules:
  [`docs/standards/`](standards/)

Code-adjacent docs should own bounded package responsibility. Repo-wide docs
should own cross-package, cross-tool, or cross-repo meaning.

## Responsibility Boundary

`mycite-core` owns:

- portal authority and capability semantics
- runtime contracts and tool mediation
- cross-domain semantic services
- SQL-backed authority posture
- narrow audited write seams where explicitly approved

`mycite-core` does not own:

- NGINX, Keycloak, oauth2-proxy, Redis, or Docker/compose host topology
- live instance state as an authoring surface
- hosted frontend assets as a source repo

Related repos and roots:

- `srv-infra` owns host/runtime topology and deployment operations
- `/srv/webapps` owns hosted frontend assets plus analytics corpora
- `/srv/mycite-state` owns mutable per-instance runtime state

## Canonical Current Truth

- universal shell/tool posture:
  [`docs/contracts/tool_operating_contract.md`](contracts/tool_operating_contract.md)
- shell composition and routes:
  [`docs/contracts/portal_shell_contract.md`](contracts/portal_shell_contract.md),
  [`docs/contracts/route_model.md`](contracts/route_model.md),
  [`docs/contracts/surface_catalog.md`](contracts/surface_catalog.md)
- vocabulary:
  [`docs/contracts/portal_vocabulary_glossary.md`](contracts/portal_vocabulary_glossary.md)
- structural and mutation posture:
  [`docs/contracts/samras_structural_model.md`](contracts/samras_structural_model.md),
  [`docs/contracts/samras_validity_and_mutation.md`](contracts/samras_validity_and_mutation.md),
  [`docs/contracts/mutation_contract.md`](contracts/mutation_contract.md)
- planning system posture:
  [`docs/plans/README.md`](plans/README.md)

## Preservation Rule

This alignment pass is intentionally lossless:

- personal notes stay preserved
- audits and reports stay preserved
- historical plans stay preserved
- new indexes and wiki/orientation pages reduce drift without deleting source material
