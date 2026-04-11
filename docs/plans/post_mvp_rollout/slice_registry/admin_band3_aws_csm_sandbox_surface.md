# Slice ID

`admin_band3.aws_csm_sandbox_surface`

## Status

`implemented_internal_sandbox_read_only`

## Record-only note

This slice is already implemented. Keep this file only as slice-spec history.
Use [../../../records/T-008-implementation.md](../../../records/T-008-implementation.md) for completion evidence and [../current_planning_index.md](../current_planning_index.md) for current active planning.

## Purpose

Provide an **internal-only** read-only AWS-CSM projection against a **separate**
staged profile file (`mycite.service_tool.aws_csm.profile.v1`), orchestrated
through `MyCiteV2/packages/sandboxes/tool/` without conflating sandbox paths
with trusted-tenant production AWS slices.

## Client value

Operators can validate staging or copied profiles in the same portal shell UX
as production read-only, with explicit audience and path separation.

## Rollout band

`Admin Band 3 Internal AWS-CSM Sandbox`

## Exposure status

`internal_sandbox_read_only`

## Configuration

- **`MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE`**: optional path to a sandbox/staging
  profile JSON. Independent of **`MYCITE_V2_AWS_STATUS_FILE`** used by
  `admin_band1.aws_read_only_surface` and `_required_live_aws_status_file` on
  trusted-tenant POST routes.
- Portal route **`POST /portal/api/v2/admin/aws/csm-sandbox/read-only`** uses
  only the sandbox env path (returns `503` when unset or not a valid live
  profile document).

## Owning layers

- `packages/sandboxes/tool/` — path validation orchestration only
- `packages/modules/cross_domain/aws_operational_visibility/` — semantic read
- `packages/adapters/filesystem/live_aws_profile.py` — adapter when file validates
- `instances/_shared/runtime/admin_aws_runtime.py` — `run_admin_aws_csm_sandbox_read_only`
- `packages/state_machine/hanus_shell/admin_shell.py` — registry + launch resolution

## Required ports

- `packages/ports/aws_read_only_status/` (reuse)

## Required adapters

- `FilesystemLiveAwsProfileAdapter` when `is_live_aws_profile_file` succeeds

## Required runtime composition

- Entrypoint: `admin.aws.csm_sandbox_read_only`
- Launchable only for **internal** audience; **trusted-tenant** requests are denied at launch resolution

## Required tests

- Integration: sandbox runtime + shell entry + production AWS unchanged
- Architecture: `sandboxes/tool` import boundaries

## Client exposure gates

- Internal audience only for this slice
- No narrow write on this slice (read-only registry posture)
- Production Band 1 / Band 2 behavior and slice IDs must remain unchanged

## Out of scope

- Replacing `MYCITE_V2_AWS_STATUS_FILE` for production routes
- Broad provider-admin surfaces

## V1 evidence

- `MyCiteV1/packages/tools/aws_csm/` — evidence only; not copied as structure
