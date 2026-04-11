# T-007 Investigation: AWS-CSM sandbox tool surface

## 1. Repo findings

### 1.1 What already exists (AWS read-only / bounded-write platform)

- **Pattern authority:** `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md` defines the two approved seams (`admin_band1.aws_read_only_surface`, `admin_band2.aws_narrow_write_surface`) and the ownership split (semantic owner, port, adapter, runtime entrypoint, shell registry descriptor).

- **Shell registry and gating:** `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` exposes exactly two AWS tool entries via `build_admin_tool_registry_entries()` (`aws` → read-only slice, `aws_narrow_write` → narrow-write slice). `resolve_admin_shell_request` limits `trusted-tenant` audiences to registry-backed tool slices (plus datum). Composition helpers (`shell_composition_mode_for_surface`, `map_surface_to_active_service`) treat only those two slice IDs as **tool mode** / `active_service: "aws"`.

- **Runtime entrypoints:** `MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py` implements `run_admin_aws_read_only` and `run_admin_aws_narrow_write`, wiring `resolve_admin_tool_launch`, semantic services (`AwsOperationalVisibilityService`, `AwsNarrowWriteService`, `LocalAuditService`), and filesystem adapters. Live profile IO uses `FilesystemLiveAwsProfileAdapter` when `is_live_aws_profile_file` is true (JSON on disk with schema `mycite.service_tool.aws_csm.profile.v1`).

- **Portal host HTTP surface:** `MyCiteV2/instances/_shared/portal_host/app.py` mounts `POST /portal/api/v2/admin/shell`, `.../admin/aws/read-only`, and `.../admin/aws/narrow-write`. AWS JSON routes pass `aws_status_file=_required_live_aws_status_file(host_config)`, which returns a path **only** when `is_live_aws_profile_file` succeeds (file exists and schema matches). Shell entry receives `host_config.aws_status_file` without that extra gate (composition can still embed read-only context paths used by runtime branches).

- **Wire contract for tools:** `MyCiteV2/docs/contracts/shell_region_kinds.md` documents current workbench/inspector kinds for AWS (`tool_placeholder`, `aws_read_only_surface`, `aws_tool_error`, `narrow_write_form`) and explicitly lists extension steps for new tools (registry, dispatch bodies, `_build_regions_and_surface`, JS branches).

- **Sandboxes package (orchestration boundary):** `MyCiteV2/packages/sandboxes/` exists with `module_contract.md` and ADR `MyCiteV2/docs/decisions/decision_record_0006_sandboxes_are_orchestration_boundaries.md` (sandboxes coordinate staging/mediation; they do not own domain or shell truth). `packages/sandboxes/tool/README.md` is explicitly a **placeholder** (“tool-scoped orchestration boundaries only”) with no implementation.

- **Legacy V1 CSM tool code:** `MyCiteV1/packages/tools/aws_csm/` exists (e.g. `state_adapter/paths.py` resolving `aws-csm` under shared tool state). There is **no** `MyCiteV2/packages/tools/aws_csm/` tree; V2 instead uses cross-domain modules + `packages/adapters/filesystem/live_aws_profile.py` for the same **profile schema**, not a ported tool package.

- **Operational docs:** Plans under `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/` describe `MYCITE_V2_AWS_STATUS_FILE` pointing at canonical live `aws-csm.*.json` profiles for the Shape B bridge. `future_tool_drop_in_contract.md` still lists sandboxes as **outside** the current AWS platform track until explicitly approved.

### 1.2 Existing seams vs missing seams (summary)

| Seam | Status |
|------|--------|
| Shell-owned tool registry for **production-trusted** AWS read-only / narrow-write | Present |
| Semantic + port + adapter stack for `aws_csm.profile.v1` mapping and narrow field writeback | Present |
| Admin runtime + portal routes for those two entrypoints | Present |
| **Sandbox orchestration** (`packages/sandboxes/tool`) coordinating staged profiles, mediation, or non-production artifact roots | **Missing** (placeholder README only) |
| **Dedicated shell slice / registry entry / entrypoint** for “AWS-CSM sandbox” distinct from the two trusted-tenant AWS slices | **Missing** |
| **Host configuration** for a second, explicitly non-canonical profile root (e.g. staging directory) with the same portal UX guarantees as production | Not defined in V2 repo (single `MYCITE_V2_AWS_STATUS_FILE` pattern today) |

## 2. Changes made

None. Investigation-only task; no product code edits.

## 3. Tests run

Not applicable for this investigation deliverable.

## 4. Deploy findings

Not inspected. Task scope lists no `live_systems`. Current repo docs emphasize `MYCITE_V2_AWS_STATUS_FILE` for canonical live profiles only.

## 5. Live verification

Not applicable.

## 6. Gap analysis (what is missing for an AWS-CSM **sandbox** workflow)

1. **Orchestration layer:** ADR 0006 reserves `packages/sandboxes/` for staging/mediation. There is no code that uses `sandboxes.tool` to stage `aws_csm.profile.v1` artifacts, validate them, or hand off to a bounded write, without conflating that with production shell truth.

2. **Shell / registry / composition:** The admin shell has no third tool for “sandbox” or “staging CSM” — only `admin_band1.aws_read_only_surface` and `admin_band2.aws_narrow_write_surface`. Any sandbox workflow would need new slice id(s), registry entries, `resolve_admin_*` updates, `run_admin_shell_entry` / region builder branches, and likely `v2_portal_shell.js` / contract doc updates so the client does not invent navigation.

3. **Configuration contract:** Operations today assume one canonical status file per host. A sandbox workflow needs an explicit repo contract for **where** sandbox profiles live (env var, path convention), how they differ from `MYCITE_V2_AWS_STATUS_FILE`, and whether portal routes are shared, namespaced, or internal-audience-only — none of which is specified in current V2 code beyond the live-profile gate on AWS POST routes.

4. **V1 parity / migration:** V1’s `packages/tools/aws_csm` path helpers and tool state layout are evidence only; they are not replicated as a V2 tool module. The “missing” piece is not the schema (already shared) but the **orchestrated sandbox-facing workflow** and shell surfacing.

## 7. Classification of missing work

- **Primary implementation (orchestration + shell slice + runtime + tests + docs):** **`repo_only`**. Can be fully exercised with temp directories, pytest, and architecture boundary tests without requiring a live URL.

- **Optional follow-on:** If acceptance later includes “operators use sandbox on deployed hosts with separate paths,” that becomes **`repo_and_deploy`** (new env vars, systemd, nginx not required unless routes change, verifier with host/live transcripts per `tasks/README.md` §9.3).

## 8. Repo paths likely to change (for follow-on T-008)

- `MyCiteV2/packages/sandboxes/tool/` (new orchestration module(s), `__init__.py` beyond placeholder)
- `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` (registry, dispatch bodies, composition maps)
- `MyCiteV2/instances/_shared/runtime/admin_runtime.py` and possibly `admin_aws_runtime.py` (entrypoints, region builders)
- `MyCiteV2/instances/_shared/portal_host/app.py` (routes and/or config for sandbox profile root; audience gating)
- `MyCiteV2/instances/_shared/portal_host/static/v2_portal_shell.js` (if new inspector/workbench kinds or routes)
- `MyCiteV2/docs/contracts/shell_region_kinds.md` and a new or updated slice doc under `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/`
- `MyCiteV2/tests/integration/`, `MyCiteV2/tests/architecture/` (new loops per `future_tool_drop_in_contract.md`)

## 9. Recommended next task

See `tasks/T-008-aws-csm-sandbox-tool.yaml` — single implementation task authored from this report.
