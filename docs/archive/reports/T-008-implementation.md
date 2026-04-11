# T-008 implementation report

**Task:** T-008 — AWS-CSM sandbox tool orchestration and shell surface  
**Role:** implementer  
**Date:** 2026-04-11

---

## 1. Files changed

| Path | Change type |
|------|-------------|
| `MyCiteV2/packages/sandboxes/tool/aws_csm_staging.py` | structural (new) |
| `MyCiteV2/packages/sandboxes/tool/__init__.py` | structural |
| `MyCiteV2/packages/sandboxes/tool/README.md` | documentation |
| `MyCiteV2/packages/state_machine/hanus_shell/admin_shell.py` | structural |
| `MyCiteV2/packages/state_machine/hanus_shell/__init__.py` | structural |
| `MyCiteV2/instances/_shared/runtime/admin_aws_runtime.py` | runtime |
| `MyCiteV2/instances/_shared/runtime/admin_runtime.py` | runtime |
| `MyCiteV2/instances/_shared/runtime/runtime_platform.py` | runtime |
| `MyCiteV2/instances/_shared/portal_host/app.py` | runtime / template-adjacent config |
| `MyCiteV2/packages/adapters/portal_runtime/v1_host_bridge.py` | runtime |
| `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/admin_band3_aws_csm_sandbox_surface.md` | documentation |
| `MyCiteV2/docs/plans/post_mvp_rollout/slice_registry/README.md` | documentation |
| `MyCiteV2/docs/plans/post_mvp_rollout/runtime_entrypoints.md` | documentation |
| `MyCiteV2/docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md` | documentation |
| `MyCiteV2/docs/contracts/shell_region_kinds.md` | documentation |
| `MyCiteV2/tests/architecture/test_runtime_composition_boundaries.py` | test-only |
| `MyCiteV2/tests/architecture/test_sandboxes_tool_boundaries.py` | test-only (new) |
| `MyCiteV2/tests/integration/test_admin_aws_csm_sandbox_runtime.py` | test-only (new) |
| `MyCiteV2/tests/integration/test_admin_runtime_composition.py` | test-only |
| `MyCiteV2/tests/integration/test_admin_runtime_platform_contracts.py` | test-only |
| `MyCiteV2/tests/integration/test_v2_deployment_bridge_shape_b.py` | test-only |
| `MyCiteV2/tests/integration/test_v2_native_portal_host.py` | test-only |
| `MyCiteV2/tests/unit/test_admin_tool_platform_contract.py` | test-only |
| `MyCiteV2/tests/unit/test_state_machine_admin_shell.py` | test-only |
| `tasks/T-008-aws-csm-sandbox-tool.yaml` | documentation (lifecycle + `repo_test_command`) |
| `reports/T-008-implementation.md` | documentation |
| `reports/handoffs/T-008/implementer_to_verifier.md` | documentation |

---

## 2. Why each file changed

- **Sandboxes `tool/`:** ADR 0006 orchestration seam — `validate_staged_aws_csm_profile_path` delegates schema check to `is_live_aws_profile_file` (no V1 structural copy).
- **`admin_shell.py`:** Third registry entry (`aws_csm_sandbox`), slice `admin_band3.aws_csm_sandbox_surface`, entrypoint `admin.aws.csm_sandbox_read_only`, **internal-admin** audience; internal-only resolution path; launch guards so **internal** cannot launch trusted production AWS entrypoints at `resolve_admin_tool_launch` and **trusted-tenant** cannot launch sandbox; composition maps treat sandbox like other AWS tool slices; dispatch bodies use **internal** `tenant_scope` for sandbox.
- **`admin_aws_runtime.py`:** `run_admin_aws_csm_sandbox_read_only` — internal audience, sandbox path validation via sandboxes package, reuse read-only surface builder with `active_surface_id` override.
- **`admin_runtime.py`:** `run_admin_shell_entry(..., aws_csm_sandbox_status_file=...)` and `_build_regions_and_surface` branch for sandbox slice (same inspector kinds as read-only).
- **`runtime_platform.py`:** Catalog entry for sandbox entrypoint + `required_configuration`.
- **`app.py`:** `MYCITE_V2_AWS_CSM_SANDBOX_STATUS_FILE` on `V2PortalHostConfig`; `POST /portal/api/v2/admin/aws/csm-sandbox/read-only` (separate from `_required_live_aws_status_file`); health `aws_config_health` extensions; URL slug `aws-csm-sandbox`.
- **`v1_host_bridge.py`:** Optional `aws_csm_sandbox_status_file` on bridge config; dispatch + health `configured_inputs` keys; status mapping for `sandbox_profile_invalid`.
- **Docs / slice registry:** Record band, env semantics, and runtime entrypoint row.
- **Tests:** Coverage for registry, launch gates, shell entry, architecture boundaries; relaxed runtime import test to allow **`MyCiteV2.packages.sandboxes.tool`** only.

---

## 3. Commands run

Canonical **`execution.repo_test_command`** from `tasks/T-008-aws-csm-sandbox-tool.yaml` (verbatim):

```text
cd /srv/repo/mycite-core && PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest \
  MyCiteV2.tests.architecture.test_state_machine_boundaries \
  MyCiteV2.tests.architecture.test_runtime_composition_boundaries \
  MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries \
  MyCiteV2.tests.integration.test_admin_aws_read_only_runtime \
  MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime \
  MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime -v
```

Exit code **0** (20 tests).

Additional modules exercised locally after related edits:

```text
MyCiteV2.tests.unit.test_admin_tool_platform_contract
MyCiteV2.tests.unit.test_state_machine_admin_shell
MyCiteV2.tests.integration.test_admin_runtime_composition
MyCiteV2.tests.integration.test_admin_runtime_platform_contracts
MyCiteV2.tests.integration.test_v2_native_portal_host
MyCiteV2.tests.integration.test_v2_deployment_bridge_shape_b
```

Exit code **0** (34 tests in that batch).

---

## 4. Tests run

See **§3**.

---

## 5. Deploy actions taken

None (`primary_type: repo_only`).

---

## 6. What still requires independent verification

Verifier should re-run **`execution.repo_test_command`** exactly as in **`tasks/T-008-aws-csm-sandbox-tool.yaml`**, paste transcripts into **`reports/T-008-verification.md`**, and confirm:

- Trusted-tenant **Band 1 / Band 2** semantics unchanged.
- Sandbox slice is **internal-only** on launch and HTTP route behavior matches docs when env unset vs valid profile.

---

## 7. Recommended next status

`status: verification_pending` (set in task YAML)  
`execution.current_role: verifier`  
`execution.next_role: lead`  
`verification_result: pending`

---

## Host / live (not applicable)

**Host:** not applicable  
**Live:** not applicable
