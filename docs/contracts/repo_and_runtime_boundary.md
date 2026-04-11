# Repo And Runtime Boundary

Authority: [../plans/v2-authority_stack.md](../plans/v2-authority_stack.md)

This file states the shared repo-vs-runtime rule that applies across the V1 to
V2 transition.

## Current contract

- Repo-owned code and repo-owned docs are the authoring surface for application
  semantics.
- Live state under `/srv/mycite-state/instances/<tenant>/` is a deployment and
  runtime surface, not the primary authoring surface.
- Host infrastructure such as `systemd`, NGINX, wrapper scripts, or external
  infra repositories may compose and deploy the runtime, but they do not define
  shell truth, domain rules, or datum semantics.
- In the current live posture, `srv-infra` is the tracked deployment-truth repo
  for those host manifests. `mycite-core/docs/` references that deployment
  truth rather than duplicating it.
- Runtime composition is allowed to wire approved layers together, choose
  adapters, and expose approved entrypoints. It is not allowed to become a new
  semantic owner.
- Migrations, materializers, and rollout bridges may update runtime state, but
  semantic changes must still start in repo code and authoritative docs.
- Deployment mirrors, copied state snapshots, compatibility symlinks, and host
  wrapper copies are never higher authority than repo docs and repo-owned code.

## Cross-version interpretation

- In V1, this boundary existed but was easy to blur because runtime wrappers and
  shared portal trees carried too much semantic weight.
- In V2, the boundary is explicit: semantics live in `docs/`, inward packages,
  and declared contracts, while runtime composition lives under
  `MyCiteV2/instances/_shared/`.

Keep the boundary. Do not promote host topology or live-state layout into
semantic authority.

## Use this doc when promoting legacy content

Promote legacy content here when it is really about:

- repo ownership vs host ownership
- live state as deployment surface
- runtime composition staying composition-only
- migration order for semantic changes

Leave content in `docs/*/legacy/` when it is really about:

- V1 wrapper lists
- V1 route/bootstrap inventories
- old compose or service topology details
- dated runtime alignment checkpoints

## Source authorities

- [../ontology/structural_invariants.md](../ontology/structural_invariants.md)
- [../decisions/decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md](../decisions/decision_record_0007_hosts_compose_but_do_not_own_domain_logic.md)
- [../plans/legacy/modularity/ownership-boundary.md](../plans/legacy/modularity/ownership-boundary.md)
- [../plans/legacy/modularity/runtime_alignment_report.md](../plans/legacy/modularity/runtime_alignment_report.md)
- [portal_auth_and_audience_boundary.md](portal_auth_and_audience_boundary.md)
- [../../MyCiteV1/README.md](../../MyCiteV1/README.md)
- [../../MyCiteV2/instances/_shared/README.md](../../MyCiteV2/instances/_shared/README.md)
