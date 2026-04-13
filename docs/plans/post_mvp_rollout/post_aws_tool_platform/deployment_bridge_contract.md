# V2 Deployment Bridge Contract

Authority: [../../v2-authority_stack.md](../../v2-authority_stack.md)

This document records the bridge design that made the tested V2 admin runtime
reachable from the live portal during cutover without recreating V1 route
drift.

Implementation status: historical cutover design. Shape B was implemented by
`MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py` during the bridge
era before the V2-native portal host became the live boundary. The bridge is
now quarantined historical evidence. Do not use this document as an active
implementation path.

## Historical goal

Expose the V2 admin shell and cataloged AWS admin runtime entrypoints through the live portal boundary while keeping V1 and V2 as isolated directories.

## Historical outcome

- `/srv/repo/mycite-core/` contains only explicit `MyCiteV1/` and `MyCiteV2/` code roots.
- The live web boundary called `admin.shell_entry`.
- The live web boundary called `admin.aws.read_only`.
- The live web boundary called `admin.aws.narrow_write` only through the existing shell-owned launch legality.
- No root compatibility package path is required.
- No direct provider-admin V2 route becomes a second source of truth.

## Historical implementation note

The bridge-era cutover implemented Shape B: a very small V1-host bridge that
called cataloged V2 runtime entrypoints by explicit path. Shape selection is no
longer open. The live canonical boundary is now the V2-native host under
`MyCiteV2/instances/_shared/portal_host/`.

## Implemented bridge routes

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

The AWS routes required explicit configured V2-compatible AWS status input.
That requirement now lives on as a native-host rule in
[live_state_authority_and_mapping.md](live_state_authority_and_mapping.md).

## Historical constraints that still matter

- no dynamic package discovery
- no route-level parity porting from V1 admin providers
- no broad `/portal/api/admin/aws/*` recreation as the V2 surface
- no direct CTS-GIS or AGRO-ERP bridge routes
- no write path that bypasses `admin.aws.narrow_write`
- no duplicated shell registry in V1
- no root-level compatibility symlinks

## Historical proof retained

- bridge route tests proving V2 runtime entrypoints were called
- denied-launch tests for unknown slices
- audience-denied tests for non-approved audiences
- no-secret serialization tests for bridge responses
- architecture evidence proving the bridge imported only the V2 runtime surface and did not scan packages
- regression evidence for the already-implemented V2 Admin Band 0 and AWS slices

## Current rule

Use [../current_planning_index.md](../current_planning_index.md) and
[../../../records/22-v1_retirement_closure.md](../../../records/22-v1_retirement_closure.md)
for the current canonical sequence. This bridge contract is record-only.
