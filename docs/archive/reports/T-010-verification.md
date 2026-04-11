# Verification report

**Task:** T-010 — Implement V2 shell-owned AWS-CSM mailbox onboarding workflow (V1 provision parity)  
**Role:** verifier  
**Date:** 2026-04-11

**Task type:** `repo_only` (host and live layers: **not applicable** per task scope).

---

## 1. Exact commands used

```text
cd /srv/repo/mycite-core && PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest MyCiteV2.tests.architecture.test_state_machine_boundaries MyCiteV2.tests.architecture.test_runtime_composition_boundaries MyCiteV2.tests.architecture.test_sandboxes_tool_boundaries MyCiteV2.tests.integration.test_admin_aws_read_only_runtime MyCiteV2.tests.integration.test_admin_aws_narrow_write_runtime MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime MyCiteV2.tests.unit.test_admin_tool_platform_contract MyCiteV2.tests.unit.test_state_machine_admin_shell MyCiteV2.tests.integration.test_admin_runtime_composition MyCiteV2.tests.integration.test_admin_runtime_platform_contracts -v
```

(This is `execution.repo_test_command` from `tasks/T-010-v2-aws-csm-onboarding-workflow.yaml` after YAML `>-` folding to one shell line.)

Supplemental repo checks (confirm acceptance; captured 2026-04-11):

```text
grep -E 'provision|admin/aws/profile' /srv/repo/mycite-core/MyCiteV2/instances/_shared/portal_host/app.py; echo "exit:$?"
```

```text
exit:1
```

(`grep` exit status **1** = no lines matched; stdout empty.)

```text
grep -Ri 'mycitev1' /srv/repo/mycite-core/MyCiteV2/packages/modules/cross_domain/aws_csm_onboarding/; echo "exit:$?"
```

```text
exit:1
```

---

## 2. Exact captured stdout/stderr

### 2.1 `unittest` (canonical `repo_test_command`)

```text
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
test_registry_surface_lists_all_catalog_tools (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_registry_surface_lists_all_catalog_tools) ... ok
test_sandbox_read_only_happy_path (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_sandbox_read_only_happy_path) ... ok
test_shell_entry_allows_internal_sandbox_surface (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_shell_entry_allows_internal_sandbox_surface) ... ok
test_trusted_tenant_cannot_launch_sandbox_slice (MyCiteV2.tests.integration.test_admin_aws_csm_sandbox_runtime.AdminAwsCsmSandboxRuntimeIntegrationTests.test_trusted_tenant_cannot_launch_sandbox_slice) ... ok
test_begin_onboarding_applies_audit_and_read_after_write (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_begin_onboarding_applies_audit_and_read_after_write) ... ok
test_confirm_verified_fail_closed_without_cloud_evidence (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_confirm_verified_fail_closed_without_cloud_evidence) ... ok
test_confirm_verified_succeeds_when_cloud_port_attests_evidence (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_confirm_verified_succeeds_when_cloud_port_attests_evidence) ... ok
test_internal_audience_cannot_launch_onboarding_slice (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_internal_audience_cannot_launch_onboarding_slice) ... ok
test_registry_includes_onboarding_tool_for_trusted_tenant (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_registry_includes_onboarding_tool_for_trusted_tenant) ... ok
test_replay_verification_forward_is_policy_blocked (MyCiteV2.tests.integration.test_admin_aws_csm_onboarding_runtime.AdminAwsCsmOnboardingRuntimeIntegrationTests.test_replay_verification_forward_is_policy_blocked) ... ok
test_descriptor_rejects_writable_tool_without_audit_or_read_after_write (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_descriptor_rejects_writable_tool_without_audit_or_read_after_write) ... ok
test_runtime_entrypoint_catalog_is_static_and_serializable (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_runtime_entrypoint_catalog_is_static_and_serializable) ... ok
test_shared_runtime_envelope_shape_is_fixed (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_shared_runtime_envelope_shape_is_fixed) ... ok
test_tool_descriptors_have_stable_drop_in_shape (MyCiteV2.tests.unit.test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_tool_descriptors_have_stable_drop_in_shape) ... ok
test_band_name_is_fixed_for_admin_band0 (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_band_name_is_fixed_for_admin_band0) ... ok
test_catalog_and_registry_are_serializable_and_shell_owned (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_catalog_and_registry_are_serializable_and_shell_owned) ... ok
test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant) ... ok
test_non_internal_audience_is_denied_for_admin_band0 (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_non_internal_audience_is_denied_for_admin_band0) ... ok
test_request_contract_rejects_invalid_schema_and_audience (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_request_contract_rejects_invalid_schema_and_audience) ... ok
test_request_defaults_to_internal_home_status (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_request_defaults_to_internal_home_status) ... ok
test_shell_chrome_round_trips_in_request_dict (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_shell_chrome_round_trips_in_request_dict) ... ok
test_shell_entry_alias_resolves_to_home_status (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_shell_entry_alias_resolves_to_home_status) ... ok
test_tool_registry_surface_is_available_and_aws_redirects_to_registry (MyCiteV2.tests.unit.test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_tool_registry_surface_is_available_and_aws_redirects_to_registry) ... ok
test_default_admin_shell_entry_returns_internal_home_status (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_default_admin_shell_entry_returns_internal_home_status) ... ok
test_non_internal_request_is_denied_without_surface_payload (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_non_internal_request_is_denied_without_surface_payload) ... ok
test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline) ... ok
test_shell_chrome_mediates_inspector_collapse_in_tool_mode (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_shell_chrome_mediates_inspector_collapse_in_tool_mode) ... ok
test_tool_registry_surface_is_catalog_driven_and_deny_by_default (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_tool_registry_surface_is_catalog_driven_and_deny_by_default) ... ok
test_trusted_tenant_aws_read_only_slice_composes_tool_mode (MyCiteV2.tests.integration.test_admin_runtime_composition.AdminRuntimeCompositionTests.test_trusted_tenant_aws_read_only_slice_composes_tool_mode) ... ok
test_current_admin_entrypoints_return_shared_envelope_shape (MyCiteV2.tests.integration.test_admin_runtime_platform_contracts.AdminRuntimePlatformIntegrationTests.test_current_admin_entrypoints_return_shared_envelope_shape) ... ok
test_tool_registry_descriptors_match_runtime_entrypoint_ids (MyCiteV2.tests.integration.test_admin_runtime_platform_contracts.AdminRuntimePlatformIntegrationTests.test_tool_registry_descriptors_match_runtime_entrypoint_ids) ... ok

----------------------------------------------------------------------
Ran 47 tests in 0.107s

OK

```

Shell exit code: **0**.

---

## 3. Acceptance mapping: pass/fail by criterion

| Criterion | Result | Notes |
|-----------|--------|-------|
| T-009 parity in code or `replay_verification_forward` deferred with documented default + tests | **pass** | `test_replay_verification_forward_is_policy_blocked`; implementation report documents omission |
| All listed V1 actions have named V2 mapping in implementation report | **pass** | `reports/T-010-implementation.md` mapping table |
| No new routes copying V1 `/portal/api/admin/aws/profile/<id>/provision` | **pass** | §1 `app.py` grep empty; v2 route `POST /portal/api/v2/admin/aws/csm-onboarding` present in repo |
| Shell composition authoritative; client JS only renders server-issued requests | **pass** | `v2_portal_shell.js` uses `submit_contract` / `contract.route` for POST body and URL |
| Band 1/2/3 (T-008) unittest modules still pass | **pass** | §2.1 includes read-only, narrow-write, sandbox modules — all `ok` |
| `execution.repo_test_command` passes independently | **pass** | §2.1, exit 0 |

---

## 4. Repo/host/live mismatches

none.

(Host and live: not applicable to acceptance for this task.)

---

## 5. Final verdict

**PASS** — Canonical unittest command exited 0 with 47/47 tests OK; repo spot-checks support route-shape and no-V1-import acceptance; no contradictions found between evidence and task acceptance for `repo_only` scope.

---

## 6. Recommended next status

`verified_pass` / `verification_result: pass` (task YAML updated). Lead may set `status: resolved` per `closure_rule` after review.
