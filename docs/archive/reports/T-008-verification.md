# T-008 Verification report

**Task:** T-008 — Implement AWS-CSM sandbox tool orchestration and shell-facing surface  
**Role:** verifier  
**Date:** 2026-04-11

---

## 1. Exact commands used

Canonical `execution.repo_test_command` from `tasks/T-008-aws-csm-sandbox-tool.yaml` (single shell invocation, no line continuations):

```bash
cd /srv/repo/mycite-core && PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries MyCiteV2.tests.architecture.test_runtime_composition_boundaries MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries MyCiteV2.tests.integration.test_admin_aws_read_only_runtime MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime -v
```

Supplemental repo inspection (structure only):

```bash
ls -la /srv/repo/mycite-core/MyCiteV2/packages/sandboxes/tool/
```

---

## 2. Exact captured stdout/stderr

### 2.1 `unittest` (canonical command)

```
test_imports_remain_inward_core_or_state_machine_only (MyCiteV2.tests.architecture.test_state_machine_boundaries.StateMachineBoundaryTests.test_imports_remain_inward_core_or_state_machine_only) ... ok
test_source_contains_no_runtime_tool_or_sandbox_leakage (MyCiteV2.tests.architecture.test_state_machine_boundaries.StateMachineBoundaryTests.test_source_contains_no_runtime_tool_or_sandbox_leakage) ... ok
test_runtime_imports_compose_inward_layers_only (MyCiteV2.tests.architecture.test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_imports_compose_inward_layers_only) ... ok
test_runtime_source_contains_no_framework_or_legacy_provider_logic (MyCiteV2.tests.architecture.test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_source_contains_no_framework_or_legacy_provider_logic) ... ok
test_runtime_surface_stays_single_path_without_flavor_expansion (MyCiteV2.tests.architecture.test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_surface_stays_single_path_without_flavor_expansion) ... ok
test_tool_sandbox_imports_stay_orchestration_only (MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries.SandboxesToolBoundaryTests.test_tool_sandbox_imports_stay_orchestration_only) ... ok
test_live_aws_profile_file_is_mapped_at_runtime (MyCiteV2.tests.integration.test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_live_aws_profile_file_is_mapped_at_runtime) ... ok
test_missing_status_source_is_reported_explicitly (MyCiteV2.tests.integration.test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_missing_status_source_is_reported_explicitly) ... ok
test_shell_registry_entry_launches_aws_read_only_entrypoint (MyCiteV2.tests.integration.test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_shell_registry_entry_launches_aws_read_only_entrypoint) ... ok
test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged) ... ok
test_live_aws_profile_narrow_write_updates_canonical_live_artifact (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_live_aws_profile_narrow_write_updates_canonical_live_artifact) ... ok
test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit) ... ok
test_write_requires_audit_path_before_applying (MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_write_requires_audit_path_before_applying) ... ok
test_internal_cannot_launch_production_read_only_via_registry_launch (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_internal_cannot_launch_production_read_only_via_registry_launch) ... ok
test_production_read_only_unchanged_for_trusted_tenant (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_production_read_only_unchanged_for_trusted_tenant) ... ok
test_registry_includes_distinct_sandbox_descriptor (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_registry_includes_distinct_sandbox_descriptor) ... ok
test_registry_surface_lists_three_tools (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_registry_surface_lists_three_tools) ... ok
test_sandbox_read_only_happy_path (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_sandbox_read_only_happy_path) ... ok
test_shell_entry_allows_internal_sandbox_surface (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_shell_entry_allows_internal_sandbox_surface) ... ok
test_trusted_tenant_cannot_launch_sandbox_slice (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_trusted_tenant_cannot_launch_sandbox_slice) ... ok

----------------------------------------------------------------------
Ran 20 tests in 0.063s

OK
```

Exit code: **0**.

### 2.2 `ls` (sandboxes package)

```
total 24
drwxrwxr-x 3 admin admin 4096 Apr 11 04:42 .
drwxrwxr-x 6 admin admin 4096 Apr 11 04:42 ..
-rw-rw-r-- 1 admin admin  549 Apr 11 04:38 README.md
-rw-rw-r-- 1 admin admin  203 Apr 11 04:38 __init__.py
drwxrwxr-x 2 admin admin 4096 Apr 11 04:42 __pycache__
-rw-rw-r-- 1 admin admin  936 Apr 11 04:38 aws_csm_staging.py
```

---

## 3. Acceptance mapping

| Acceptance criterion | Evidence | Result |
|---------------------|----------|--------|
| Sandbox orchestration under `MyCiteV2/packages/sandboxes/tool/`; architecture import boundaries | `ls` output; `test_sandboxes_tool_boundaries` + state_machine/runtime architecture tests **ok** | **pass** |
| `build_admin_tool_registry_entries` includes distinct sandbox AWS-CSM descriptor; production AWS slices unchanged | `test_registry_includes_distinct_sandbox_descriptor`, `test_registry_surface_lists_three_tools`, `test_production_read_only_unchanged_for_trusted_tenant`, read-only/narrow-write integration tests **ok** | **pass** |
| Runtime entrypoints only via shell-approved paths; fail-closed when roots/profiles invalid | `test_shell_entry_allows_internal_sandbox_surface`, `test_trusted_tenant_cannot_launch_sandbox_slice`, `test_internal_cannot_launch_production_read_only_via_registry_launch`, `test_sandbox_read_only_happy_path` **ok** | **pass** |
| pytest/unittest targets pass; architecture tests cover import boundaries | Canonical `unittest` command: **20 tests, OK** | **pass** |
| `reports/T-008-implementation.md` and `reports/T-008-verification.md` with repo / host / live separation | This file exists; implementation report exists with deploy section and explicit **Host / live (not applicable)** (`primary_type: repo_only`) | **pass** |
| `shell_region_kinds.md` updated for emitted semantics (no new kinds required) | Doc mentions sandbox slice in `composition_mode` / `tool_placeholder` rows; reuse of existing region kinds consistent with runtime | **pass** |

### Verification requirements (task YAML)

| Requirement | Result |
|--------------|--------|
| Verifier runs `execution.repo_test_command` independently | **pass** — same `PYTHONPATH`, interpreter, and module list as task YAML |
| Fail if sandbox launch without catalog guard or production AWS regression | **pass** — dedicated tests above all **ok** |

---

## 4. Repo / host / live mismatches

- **Repo:** None found versus acceptance; independent test run matches implementer’s claimed scope without contradiction.
- **Host:** not applicable (`live_systems: []`, `live_check_command: not_applicable`; no host acceptance in task).
- **Live:** not applicable.

---

## 5. Final verdict

**Verdict (required):** **PASS**

All acceptance and verification requirements for T-008 are satisfied on current repo state; canonical unittest transcript shows **OK** (20 tests).

---

## 6. Recommended next status

Lead may set `status: resolved` per `closure_rule` when ready. Task YAML: `verified_pass`, `verification_result: pass`, `execution.current_role: lead`.
