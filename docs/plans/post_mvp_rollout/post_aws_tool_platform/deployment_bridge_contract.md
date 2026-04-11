# V2 Deployment Bridge Contract

Authority: [../../authority_stack.md](../../authority_stack.md)

This document defines the smallest acceptable bridge that can make the tested V2 admin runtime reachable from the live portal without recreating V1 route drift.

Implementation status: Shape B is implemented by `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py` and mounted in the FND/TFF V1 hosts.

## Goal

Expose the V2 admin shell and cataloged AWS admin runtime entrypoints through the live portal boundary while keeping V1 and V2 as isolated directories.

## Required outcome

- `/srv/repo/mycite-core/` contains only explicit `MyCiteV1/` and `MyCiteV2/` code roots.
- The live web boundary can call `admin.shell_entry`.
- The live web boundary can call `admin.aws.read_only`.
- The live web boundary can call `admin.aws.narrow_write` only through the existing shell-owned launch legality.
- No root compatibility package path is required.
- No direct provider-admin V2 route becomes a second source of truth.

## Approved implementation shapes

Choose exactly one.

### Shape A: V2-Owned Web Host

Add a V2-owned host surface under `MyCiteV2/packages/adapters/portal_runtime/` or another approved V2 host adapter location. The host may mount HTTP routes, but it must call only cataloged V2 runtime entrypoints.

Use this shape if the goal is to run a separate V2 service behind nginx.

### Shape B: V1 Host Bridge To V2 Runtime

Add a very small bridge in the existing V1 host that imports and calls V2 runtime entrypoints by explicit path. The bridge may only translate request/response transport. It may not copy V2 shell legality, AWS semantics, or runtime catalog decisions into V1.

Use this shape if the goal is the fastest operational cutover with the fewest prompts.

## Required bridge routes

The route names may be adjusted by the implementing agent, but the conceptual surface is fixed:

- one admin shell entry route for `admin.shell_entry`
- one AWS read-only launch route for `admin.aws.read_only`
- one AWS narrow-write launch route for `admin.aws.narrow_write`
- one health or readiness route proving V2 bridge wiring without exposing secret-bearing payloads

Implemented route surface:

- `GET /portal/api/v2/admin/bridge/health`
- `POST /portal/api/v2/admin/shell`
- `POST /portal/api/v2/admin/aws/read-only`
- `POST /portal/api/v2/admin/aws/narrow-write`

The AWS routes require explicit configured V2-compatible AWS status input. They must not be treated as live trusted-tenant AWS exposure until [live_state_authority_and_mapping.md](live_state_authority_and_mapping.md) is implemented.

## Forbidden bridge behavior

- no dynamic package discovery
- no route-level parity porting from V1 admin providers
- no broad `/portal/api/admin/aws/*` recreation as the V2 surface
- no direct Maps or AGRO-ERP bridge routes
- no write path that bypasses `admin.aws.narrow_write`
- no duplicated shell registry in V1
- no root-level compatibility symlinks

## Required tests

- bridge route tests proving V2 runtime entrypoints are called
- denied-launch tests for unknown slices
- audience-denied tests for non-approved audiences
- no-secret serialization tests for bridge responses
- architecture test proving the bridge imports only the V2 runtime surface and does not scan packages
- regression tests for all existing V2 Admin Band 0 and AWS slices

## Handoff Prompt

```text
Work only inside `MyCiteV2/` unless the chosen bridge shape explicitly requires a tiny V1 host mount.

Implement the V2 deployment bridge only.

Read first:
- `MyCiteV2/docs/plans/authority_stack.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/README.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/deployment_bridge_contract.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/live_state_authority_and_mapping.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/cutover_execution_sequence.md`
- `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band0_v2_deployment_bridge.md`
- current V2 Admin Band 0 and AWS tests

Pick Shape B unless there is an explicit reason to build a separate V2 service.

Expose only cataloged V2 runtime entrypoints:
- `admin.shell_entry`
- `admin.aws.read_only`
- `admin.aws.narrow_write`

Do not add dynamic discovery, route parity, Maps, AGRO-ERP, root compatibility symlinks, or duplicate write state.
Run V2 unit, contract, adapter, integration, and architecture tests plus bridge-specific tests.
Return exact files changed, route surface added, tests run, and remaining deployment steps.
```
