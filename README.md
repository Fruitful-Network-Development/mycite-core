# mycite-core

Canonical source for MyCiteV1 history, MyCiteV2 implementation, and the
authoritative V2 documentation tree.

## Runtime Boundaries

- V1 repo code lives under `/srv/repo/mycite-core/MyCiteV1`
- V2 repo code lives under `/srv/repo/mycite-core/MyCiteV2`
- Root-level legacy code directories are intentionally absent; use the explicit V1 or V2 root
- Live instance state lives under `/srv/mycite-state/instances/<instance_id>/`
- Portal runtime is file-backed; there is no application database in the portal core
- Native runtime is systemd-first for live FND and TFF portals; the live `/portal` host is V2-native, while V1 remains in-repo as migration evidence and retirement-review scope
- `/srv/compose/portals/` is now limited to auth-support infrastructure and transitional host files

## Canonical Authority

- `private/config.json` controls tool exposure, mount target, and utility collection selection
- `private/utilities/tools/<tool>/` holds non-datum tool specs, profile JSON, audit files, and other tool-local utility data
- `data/sandbox/<tool>/` is the authoritative tool datum root
- `data/payloads/*.bin` and `data/payloads/cache/*.json` are the only binary and decoded-payload authority roots
- Tool code does not live in instance state; canonical V1 tool code lives in [`MyCiteV1/packages/tools/`](MyCiteV1/packages/tools)
- Hosted webapp operational data is served from `/srv/webapps/<domain>/`: newsletter contact logs under `contact/`, and FND-EBI analytics under `analytics/`

## Repository Layout

- `MyCiteV1/` legacy implementation and migration evidence; not the target architecture source for new work
- `MyCiteV2/` current modular V2 code root
- `MyCiteV2/instances/_shared/portal_host/` V2-native portal host and shell assets
- `MyCiteV2/instances/_shared/runtime/` runtime entrypoint composition and admin runtime surfaces
- `MyCiteV2/packages/core/` pure structures, identities, and datum refs
- `MyCiteV2/packages/state_machine/` shell state, reducer logic, and launch legality
- `MyCiteV2/packages/ports/` boundary contracts
- `MyCiteV2/packages/adapters/` concrete filesystem and portal/runtime adapters
- `MyCiteV2/packages/modules/` domain and cross-domain use-case surfaces
- `MyCiteV2/packages/sandboxes/` orchestration and staged mediation surfaces
- `MyCiteV2/tests/` unit, contract, integration, and architecture verification loops
- `docs/` authoritative V2 contracts, ontology, plans, and records

## Key Entry Points

- V2 portal host: `MyCiteV2/instances/_shared/portal_host/app.py`
- V2 admin runtime catalog: `MyCiteV2/instances/_shared/runtime/runtime_platform.py`
- V2 admin shell entry: `MyCiteV2/instances/_shared/runtime/admin_runtime.py`
- V2 modular ownership map: `docs/contracts/v2_surface_ownership_map.md`
- V2 cutover hardening plan: `docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md`

## Canonical Docs

- [`docs/README.md`](docs/README.md) (authoritative V2 doc tree)
- [`docs/plans/v2-authority_stack.md`](docs/plans/v2-authority_stack.md)
- [`docs/contracts/v2_surface_ownership_map.md`](docs/contracts/v2_surface_ownership_map.md)
- [`docs/contracts/repo_and_runtime_boundary.md`](docs/contracts/repo_and_runtime_boundary.md)
- [`docs/contracts/tool_state_and_datum_authority.md`](docs/contracts/tool_state_and_datum_authority.md)
- [`docs/plans/post_mvp_rollout/current_planning_index.md`](docs/plans/post_mvp_rollout/current_planning_index.md)
- [`docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md`](docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md)
- [`docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md`](docs/plans/post_mvp_rollout/post_aws_tool_platform/v2_native_cutover_hardening.md)
- [`docs/plans/version-migration/README.md`](docs/plans/version-migration/README.md)
- [`docs/records/README.md`](docs/records/README.md)
- `docs/plans/legacy/`, `docs/contracts/legacy/`, and `docs/wiki/legacy/` only as audited V1 evidence

## Working Rule

Update repo code and docs first. Materialize or migrate state only through controlled scripts or explicit operational changes. Do not treat hidden compatibility paths, compose-state symlinks, or ad hoc runtime copies as equal-truth sources.
