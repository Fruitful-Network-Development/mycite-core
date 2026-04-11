# mycite-core

Canonical source for the MyCite portal core, shared runtime, tool modules, and product documentation.

## Runtime Boundaries

- V1 repo code lives under `/srv/repo/mycite-core/MyCiteV1`
- V2 repo code lives under `/srv/repo/mycite-core/MyCiteV2`
- Root-level legacy code directories are intentionally absent; use the explicit V1 or V2 root
- Live instance state lives under `/srv/mycite-state/instances/<instance_id>/`
- Portal runtime is file-backed; there is no application database in the portal core
- Native runtime is systemd-first for live FND and TFF portals; the live web host remains V1 with an internal V2 admin bridge mounted
- `/srv/compose/portals/` is now limited to auth-support infrastructure and transitional host files

## Canonical Authority

- `private/config.json` controls tool exposure, mount target, and utility collection selection
- `private/utilities/tools/<tool>/` holds non-datum tool specs, profile JSON, audit files, and other tool-local utility data
- `data/sandbox/<tool>/` is the authoritative tool datum root
- `data/payloads/*.bin` and `data/payloads/cache/*.json` are the only binary and decoded-payload authority roots
- Tool code does not live in instance state; canonical V1 tool code lives in [`MyCiteV1/packages/tools/`](MyCiteV1/packages/tools)
- Hosted webapp operational data is served from `/srv/webapps/<domain>/`: newsletter contact logs under `contact/`, and FND-EBI analytics under `analytics/`

## Repository Layout

- `MyCiteV1/instances/_shared/` shared portal and runtime code
- `MyCiteV1/instances/deployed/` repo-tracked deployed instance mirrors
- `MyCiteV1/instances/convention/` convention/reference instance artifacts
- `MyCiteV1/instances/scripts/` capture/materialization helpers
- `MyCiteV1/packages/tools/` standalone tool modules and state adapters
- `MyCiteV1/packages/core/` core data-engine and related packages
- [`docs/V1/wiki/`](docs/V1/wiki/) maintained V1 product and architecture documentation (mirror; `MyCiteV1/docs/` may be absent in some checkouts)
- [`docs/V1/plans/`](docs/V1/plans/) V1 planning snapshot
- `MyCiteV2/` isolated V2 rebuild, admin runtime, architecture gates, and rollout docs

## Key Entry Points

- Shared portal logic: `MyCiteV1/instances/_shared/portal/**`
- Flavor runtime composition: `MyCiteV1/instances/_shared/runtime/flavors/*`
- Tool build/runtime contracts: `MyCiteV1/packages/tools/_shared/**`
- Portal build script: `python3 MyCiteV1/instances/scripts/portal_build.py`
- V2 admin runtime catalog: `MyCiteV2/instances/_shared/runtime/runtime_platform.py`
- V2 admin shell entry: `MyCiteV2/instances/_shared/runtime/admin_runtime.py`

## Canonical Docs

- [`docs/V1/ownership-boundary.md`](docs/V1/ownership-boundary.md)
- [`docs/V1/wiki/README.md`](docs/V1/wiki/README.md)
- [`docs/V1/wiki/architecture/system-state-machine.md`](docs/V1/wiki/architecture/system-state-machine.md)
- [`docs/V1/wiki/data-model/datum-identity-and-resolution.md`](docs/V1/wiki/data-model/datum-identity-and-resolution.md)
- [`docs/V1/wiki/runtime-build/portal-config-model.md`](docs/V1/wiki/runtime-build/portal-config-model.md)
- [`docs/V1/wiki/tools/time-address-schema.md`](docs/V1/wiki/tools/time-address-schema.md)
- [`docs/V1/wiki/tools/internal-file-sources.md`](docs/V1/wiki/tools/internal-file-sources.md)
- [`docs/V1/plans/tool_dev.md`](docs/V1/plans/tool_dev.md)
- [`docs/README.md`](docs/README.md) (authoritative V2 doc tree)
- [`docs/plans/authority_stack.md`](docs/plans/authority_stack.md)
- [`docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md`](docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md)

## Working Rule

Update repo code and docs first. Materialize or migrate state only through controlled scripts or explicit operational changes. Do not treat hidden compatibility paths, compose-state symlinks, or ad hoc runtime copies as equal-truth sources.
