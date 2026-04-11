# Verification report

**Task:** T-006 — Add operational smoke gates for portal regression prevention  
**Role:** verifier  
**Date:** 2026-04-11

**Task type:** `repo_and_deploy`

---

## 1. Repo layer

- **`reports/T-006-smoke-gate.md`** exists and matches **`tasks/T-006-operational-smoke-and-regression-gates.yaml`**: **Step 1** `unittest` sweep over five `MyCiteV2/tests/*` trees, then **Step 2** `bash scripts/verify_v2_portal_deploy_truth.sh`; failure semantics (stop if Step 1 fails); prerequisites; explicit statement that the gate **layers** on integration tests and does **not** replace them.
- **`execution.repo_test_command`** and **`execution.live_check_command`** in the task YAML match the fenced commands in the smoke gate doc (line-for-line same structure).

Repo confirmation alone is not closure; host/live evidence is in **§2–3**.

---

## 2. Host layer

Host inspection is performed **inside Step 2** by **`verify_v2_portal_deploy_truth.sh`** (`systemctl` for **`mycite-v2-fnd-portal.service`**, **`nginx -T`** semantic grep vs repo intent). Verbatim script stdout is in **§3.2** (includes **`systemd: OK`** and **`nginx effective vs intent (grep-level): OK`**).

---

## 3. Live HTTP / operational layer

Live HTTPS and loopback shell-marker checks are performed **inside Step 2**. Verbatim script stdout is in **§3.2** (**`live static + healthz: OK`**, **`portal HTML markers: OK`** via loopback after edge OAuth HTML).

---

## 4. Exact commands used

### 4.1 Step 1 — `execution.repo_test_command` (task YAML)

```bash
cd /srv/repo/mycite-core &&
for d in MyCiteV2/tests/adapters MyCiteV2/tests/architecture MyCiteV2/tests/contracts MyCiteV2/tests/integration MyCiteV2/tests/unit; do
  echo "== $d ==" &&
  PYTHONPATH=/srv/repo/mycite-core /srv/venvs/fnd_portal/bin/python3 -m unittest discover -s "$d" -p "test*.py" -v || exit 1;
done
```

Shell recording: full stdout/stderr redirected to **`/tmp/T-006-verifier-repo-tests.log`**; shell exit **`repo_step_exit=0`** (verifier shell after the loop).

### 4.2 Step 2 — `execution.live_check_command` (task YAML)

```bash
cd /srv/repo/mycite-core &&
bash scripts/verify_v2_portal_deploy_truth.sh
```

Shell recording: full stdout/stderr redirected to **`/tmp/T-006-verifier-live-smoke.log`**; shell exit **`live_step_exit=0`**.

---

## 5. Exact captured stdout/stderr

### 5.1 Step 1 — full unittest transcript

```text
== MyCiteV2/tests/adapters ==
test_appends_payload_only_to_clients_path (test_filesystem_analytics_event_paths.AnalyticsEventPathResolverTests.test_appends_payload_only_to_clients_path) ... ok
test_rejects_unsafe_domain_or_month (test_filesystem_analytics_event_paths.AnalyticsEventPathResolverTests.test_rejects_unsafe_domain_or_month) ... ok
test_resolves_events_under_clients_domain_root (test_filesystem_analytics_event_paths.AnalyticsEventPathResolverTests.test_resolves_events_under_clients_domain_root) ... ok
test_warns_when_legacy_root_file_exists_but_stays_canonical (test_filesystem_analytics_event_paths.AnalyticsEventPathResolverTests.test_warns_when_legacy_root_file_exists_but_stays_canonical) ... ok
test_adapter_conforms_to_audit_log_port (test_filesystem_audit_log_adapter.FilesystemAuditLogAdapterTests.test_adapter_conforms_to_audit_log_port) ... ok
test_append_then_read_round_trip_matches_port_contract (test_filesystem_audit_log_adapter.FilesystemAuditLogAdapterTests.test_append_then_read_round_trip_matches_port_contract) ... ok
test_read_returns_not_found_when_storage_missing_or_id_absent (test_filesystem_audit_log_adapter.FilesystemAuditLogAdapterTests.test_read_returns_not_found_when_storage_missing_or_id_absent) ... ok
test_adapter_conforms_to_aws_narrow_write_port (test_filesystem_aws_narrow_write_adapter.FilesystemAwsNarrowWriteAdapterTests.test_adapter_conforms_to_aws_narrow_write_port) ... ok
test_apply_write_rejects_missing_snapshot_or_profile_mismatch (test_filesystem_aws_narrow_write_adapter.FilesystemAwsNarrowWriteAdapterTests.test_apply_write_rejects_missing_snapshot_or_profile_mismatch) ... ok
test_apply_write_updates_selected_verified_sender_and_reads_back (test_filesystem_aws_narrow_write_adapter.FilesystemAwsNarrowWriteAdapterTests.test_apply_write_updates_selected_verified_sender_and_reads_back) ... ok
test_adapter_conforms_to_aws_read_only_status_port (test_filesystem_aws_read_only_status_adapter.FilesystemAwsReadOnlyStatusAdapterTests.test_adapter_conforms_to_aws_read_only_status_port) ... ok
test_read_returns_expected_snapshot_for_matching_tenant (test_filesystem_aws_read_only_status_adapter.FilesystemAwsReadOnlyStatusAdapterTests.test_read_returns_expected_snapshot_for_matching_tenant) ... ok
test_read_returns_not_found_for_missing_file_or_scope_mismatch (test_filesystem_aws_read_only_status_adapter.FilesystemAwsReadOnlyStatusAdapterTests.test_read_returns_not_found_for_missing_file_or_scope_mismatch) ... ok
test_adapter_conforms_to_read_and_write_ports (test_filesystem_live_aws_profile_adapter.FilesystemLiveAwsProfileAdapterTests.test_adapter_conforms_to_read_and_write_ports) ... ok
test_narrow_write_accepts_secondary_domain_when_allowlisted (test_filesystem_live_aws_profile_adapter.FilesystemLiveAwsProfileAdapterTests.test_narrow_write_accepts_secondary_domain_when_allowlisted) ... ok
test_narrow_write_rejects_profile_mismatch_without_mutating_live_profile (test_filesystem_live_aws_profile_adapter.FilesystemLiveAwsProfileAdapterTests.test_narrow_write_rejects_profile_mismatch_without_mutating_live_profile) ... ok
test_narrow_write_updates_the_live_profile_artifact_and_reads_back (test_filesystem_live_aws_profile_adapter.FilesystemLiveAwsProfileAdapterTests.test_narrow_write_updates_the_live_profile_artifact_and_reads_back) ... ok
test_read_maps_live_profile_to_v2_visibility_shape_without_live_fields (test_filesystem_live_aws_profile_adapter.FilesystemLiveAwsProfileAdapterTests.test_read_maps_live_profile_to_v2_visibility_shape_without_live_fields) ... ok
test_read_returns_not_found_for_scope_mismatch (test_filesystem_live_aws_profile_adapter.FilesystemLiveAwsProfileAdapterTests.test_read_returns_not_found_for_scope_mismatch) ... ok
test_adapter_conforms_to_port (test_filesystem_system_datum_store_adapter.FilesystemSystemDatumStoreAdapterTests.test_adapter_conforms_to_port) ... ok
test_missing_canonical_anthology_is_unhealthy_without_root_fallback (test_filesystem_system_datum_store_adapter.FilesystemSystemDatumStoreAdapterTests.test_missing_canonical_anthology_is_unhealthy_without_root_fallback) ... ok
test_reads_canonical_system_anthology_and_ignores_legacy_root_file (test_filesystem_system_datum_store_adapter.FilesystemSystemDatumStoreAdapterTests.test_reads_canonical_system_anthology_and_ignores_legacy_root_file) ... ok

----------------------------------------------------------------------
Ran 22 tests in 0.012s

OK
== MyCiteV2/tests/architecture ==
test_imports_remain_inward_and_adapter_free (test_aws_narrow_write_boundaries.AwsNarrowWriteBoundaryTests.test_imports_remain_inward_and_adapter_free) ... ok
test_source_contains_no_broad_provider_or_secret_leakage (test_aws_narrow_write_boundaries.AwsNarrowWriteBoundaryTests.test_source_contains_no_broad_provider_or_secret_leakage) ... ok
test_imports_remain_port_only (test_aws_narrow_write_port_boundaries.AwsNarrowWritePortBoundaryTests.test_imports_remain_port_only) ... ok
test_source_contains_no_filesystem_or_broad_provider_ownership (test_aws_narrow_write_port_boundaries.AwsNarrowWritePortBoundaryTests.test_source_contains_no_filesystem_or_broad_provider_ownership) ... ok
test_imports_remain_inward_and_adapter_free (test_aws_operational_visibility_boundaries.AwsOperationalVisibilityBoundaryTests.test_imports_remain_inward_and_adapter_free) ... ok
test_source_contains_no_route_tool_or_legacy_provider_leakage (test_aws_operational_visibility_boundaries.AwsOperationalVisibilityBoundaryTests.test_source_contains_no_route_tool_or_legacy_provider_leakage) ... ok
test_imports_remain_port_only (test_aws_read_only_status_port_boundaries.AwsReadOnlyStatusPortBoundaryTests.test_imports_remain_port_only) ... ok
test_source_contains_no_filesystem_or_write_ownership_leakage (test_aws_read_only_status_port_boundaries.AwsReadOnlyStatusPortBoundaryTests.test_source_contains_no_filesystem_or_write_ownership_leakage) ... ok
test_imports_remain_inward_and_standard_library_only (test_core_datum_refs_boundaries.CoreDatumRefsBoundaryTests.test_imports_remain_inward_and_standard_library_only) ... ok
test_source_contains_no_runtime_or_instance_path_leakage (test_core_datum_refs_boundaries.CoreDatumRefsBoundaryTests.test_source_contains_no_runtime_or_instance_path_leakage) ... ok
test_imports_remain_adapter_side_without_module_semantics (test_filesystem_adapter_boundaries.FilesystemAdapterBoundaryTests.test_imports_remain_adapter_side_without_module_semantics) ... ok
test_source_contains_no_local_audit_semantic_knowledge (test_filesystem_adapter_boundaries.FilesystemAdapterBoundaryTests.test_source_contains_no_local_audit_semantic_knowledge) ... ok
test_imports_remain_adapter_side_without_semantic_ownership (test_filesystem_aws_narrow_write_boundaries.FilesystemAwsNarrowWriteBoundaryTests.test_imports_remain_adapter_side_without_semantic_ownership) ... ok
test_source_contains_no_broad_provider_or_secret_surface_knowledge (test_filesystem_aws_narrow_write_boundaries.FilesystemAwsNarrowWriteBoundaryTests.test_source_contains_no_broad_provider_or_secret_surface_knowledge) ... ok
test_imports_remain_adapter_side_without_semantic_ownership (test_filesystem_aws_read_only_status_boundaries.FilesystemAwsReadOnlyStatusBoundaryTests.test_imports_remain_adapter_side_without_semantic_ownership) ... ok
test_source_contains_no_provider_route_or_secret_surface_knowledge (test_filesystem_aws_read_only_status_boundaries.FilesystemAwsReadOnlyStatusBoundaryTests.test_source_contains_no_provider_route_or_secret_surface_knowledge) ... ok
test_imports_remain_inward_and_adapter_free (test_local_audit_boundaries.LocalAuditBoundaryTests.test_imports_remain_inward_and_adapter_free) ... ok
test_source_contains_no_runtime_tool_or_sandbox_leakage (test_local_audit_boundaries.LocalAuditBoundaryTests.test_source_contains_no_runtime_tool_or_sandbox_leakage) ... ok
test_imports_remain_port_only_and_adapter_free (test_ports_audit_log_boundaries.AuditLogPortBoundaryTests.test_imports_remain_port_only_and_adapter_free) ... ok
test_source_contains_no_runtime_filesystem_or_shell_ownership_leakage (test_ports_audit_log_boundaries.AuditLogPortBoundaryTests.test_source_contains_no_runtime_filesystem_or_shell_ownership_leakage) ... ok
test_runtime_imports_compose_inward_layers_only (test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_imports_compose_inward_layers_only) ... ok
test_runtime_source_contains_no_framework_or_legacy_provider_logic (test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_source_contains_no_framework_or_legacy_provider_logic) ... ok
test_runtime_surface_stays_single_path_without_flavor_expansion (test_runtime_composition_boundaries.RuntimeCompositionBoundaryTests.test_runtime_surface_stays_single_path_without_flavor_expansion) ... ok
test_imports_remain_inward_core_or_state_machine_only (test_state_machine_boundaries.StateMachineBoundaryTests.test_imports_remain_inward_core_or_state_machine_only) ... ok
test_source_contains_no_runtime_tool_or_sandbox_leakage (test_state_machine_boundaries.StateMachineBoundaryTests.test_source_contains_no_runtime_tool_or_sandbox_leakage) ... ok
test_bridge_uses_explicit_runtime_entrypoints_without_discovery_modules (test_v2_deployment_bridge_boundaries.V2DeploymentBridgeBoundaryTests.test_bridge_uses_explicit_runtime_entrypoints_without_discovery_modules) ... ok
test_v1_host_mount_is_limited_to_v2_bridge_registration (test_v2_deployment_bridge_boundaries.V2DeploymentBridgeBoundaryTests.test_v1_host_mount_is_limited_to_v2_bridge_registration) ... ok
test_host_does_not_expose_the_shape_b_health_route (test_v2_native_portal_host_boundaries.V2NativePortalHostBoundaryTests.test_host_does_not_expose_the_shape_b_health_route) ... ok
test_host_uses_v2_runtime_and_adapters_without_v1_imports (test_v2_native_portal_host_boundaries.V2NativePortalHostBoundaryTests.test_host_uses_v2_runtime_and_adapters_without_v1_imports) ... ok
test_portal_shell_js_has_no_fallback_catalog_nav (test_v2_native_portal_host_boundaries.V2NativePortalHostBoundaryTests.test_portal_shell_js_has_no_fallback_catalog_nav) ... ok

----------------------------------------------------------------------
Ran 30 tests in 0.182s

OK
== MyCiteV2/tests/contracts ==
test_append_receipt_and_read_request_are_explicit_and_serializable (test_audit_log_contracts.AuditLogContractTests.test_append_receipt_and_read_request_are_explicit_and_serializable) ... ok
test_append_request_accepts_one_normalized_record_payload (test_audit_log_contracts.AuditLogContractTests.test_append_request_accepts_one_normalized_record_payload) ... ok
test_append_request_rejects_non_json_or_empty_record_payloads (test_audit_log_contracts.AuditLogContractTests.test_append_request_rejects_non_json_or_empty_record_payloads) ... ok
test_read_result_supports_found_and_not_found_shapes (test_audit_log_contracts.AuditLogContractTests.test_read_result_supports_found_and_not_found_shapes) ... ok
test_record_contract_rejects_missing_identifier_or_timestamp (test_audit_log_contracts.AuditLogContractTests.test_record_contract_rejects_missing_identifier_or_timestamp) ... ok
test_request_and_result_are_explicit_and_serializable (test_aws_narrow_write_contracts.AwsNarrowWriteContractTests.test_request_and_result_are_explicit_and_serializable) ... ok
test_request_rejects_missing_fields_or_bad_sender (test_aws_narrow_write_contracts.AwsNarrowWriteContractTests.test_request_rejects_missing_fields_or_bad_sender) ... ok
test_contracts_reject_missing_scope_or_bad_payload (test_aws_read_only_status_contracts.AwsReadOnlyStatusContractTests.test_contracts_reject_missing_scope_or_bad_payload) ... ok
test_request_and_source_are_explicit_and_serializable (test_aws_read_only_status_contracts.AwsReadOnlyStatusContractTests.test_request_and_source_are_explicit_and_serializable) ... ok
test_result_supports_found_and_not_found_shapes (test_aws_read_only_status_contracts.AwsReadOnlyStatusContractTests.test_result_supports_found_and_not_found_shapes) ... ok
test_contracts_reject_missing_identity_or_non_json_raw_payload (test_system_datum_store_contracts.SystemDatumStoreContractTests.test_contracts_reject_missing_identity_or_non_json_raw_payload) ... ok
test_request_row_and_result_are_serializable (test_system_datum_store_contracts.SystemDatumStoreContractTests.test_request_row_and_result_are_serializable) ... ok

----------------------------------------------------------------------
Ran 12 tests in 0.002s

OK
== MyCiteV2/tests/integration ==
test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged (test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_live_aws_profile_denied_write_leaves_canonical_artifact_unchanged) ... ok
test_live_aws_profile_narrow_write_updates_canonical_live_artifact (test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_live_aws_profile_narrow_write_updates_canonical_live_artifact) ... ok
test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit (test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_shell_registry_entry_launches_narrow_write_with_read_after_write_and_audit) ... ok
test_write_requires_audit_path_before_applying (test_admin_aws_narrow_write_runtime.AdminAwsNarrowWriteRuntimeIntegrationTests.test_write_requires_audit_path_before_applying) ... ok
test_live_aws_profile_file_is_mapped_at_runtime (test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_live_aws_profile_file_is_mapped_at_runtime) ... ok
test_missing_status_source_is_reported_explicitly (test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_missing_status_source_is_reported_explicitly) ... ok
test_shell_registry_entry_launches_aws_read_only_entrypoint (test_admin_aws_read_only_runtime.AdminAwsReadOnlyRuntimeIntegrationTests.test_shell_registry_entry_launches_aws_read_only_entrypoint) ... ok
test_default_admin_shell_entry_returns_internal_home_status (test_admin_runtime_composition.AdminRuntimeCompositionTests.test_default_admin_shell_entry_returns_internal_home_status) ... ok
test_non_internal_request_is_denied_without_surface_payload (test_admin_runtime_composition.AdminRuntimeCompositionTests.test_non_internal_request_is_denied_without_surface_payload) ... ok
test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline (test_admin_runtime_composition.AdminRuntimeCompositionTests.test_requested_aws_slice_redirects_to_registry_and_does_not_launch_inline) ... ok
test_shell_chrome_mediates_inspector_collapse_in_tool_mode (test_admin_runtime_composition.AdminRuntimeCompositionTests.test_shell_chrome_mediates_inspector_collapse_in_tool_mode) ... ok
test_tool_registry_surface_is_catalog_driven_and_deny_by_default (test_admin_runtime_composition.AdminRuntimeCompositionTests.test_tool_registry_surface_is_catalog_driven_and_deny_by_default) ... ok
test_trusted_tenant_aws_read_only_slice_composes_tool_mode (test_admin_runtime_composition.AdminRuntimeCompositionTests.test_trusted_tenant_aws_read_only_slice_composes_tool_mode) ... ok
test_current_admin_entrypoints_return_shared_envelope_shape (test_admin_runtime_platform_contracts.AdminRuntimePlatformIntegrationTests.test_current_admin_entrypoints_return_shared_envelope_shape) ... ok
test_tool_registry_descriptors_match_runtime_entrypoint_ids (test_admin_runtime_platform_contracts.AdminRuntimePlatformIntegrationTests.test_tool_registry_descriptors_match_runtime_entrypoint_ids) ... ok
test_shell_action_to_local_audit_executes_end_to_end (test_mvp_runtime_composition.MvpRuntimeCompositionTests.test_shell_action_to_local_audit_executes_end_to_end) ... ok
test_health_builder_reports_configured_inputs_without_paths (test_v2_deployment_bridge_shape_b.V2DeploymentBridgePureAdapterTests.test_health_builder_reports_configured_inputs_without_paths) ... ok
test_bridge_denies_unknown_slices_and_non_internal_admin_band0_audience (test_v2_deployment_bridge_shape_b.V2DeploymentBridgeShapeBTests.test_bridge_denies_unknown_slices_and_non_internal_admin_band0_audience) ... ok
test_bridge_error_payload_does_not_echo_secret_bearing_request_values (test_v2_deployment_bridge_shape_b.V2DeploymentBridgeShapeBTests.test_bridge_error_payload_does_not_echo_secret_bearing_request_values) ... ok
test_bridge_maps_live_aws_profile_without_creating_shadow_status (test_v2_deployment_bridge_shape_b.V2DeploymentBridgeShapeBTests.test_bridge_maps_live_aws_profile_without_creating_shadow_status) ... ok
test_fnd_bridge_routes_call_cataloged_v2_entrypoints (test_v2_deployment_bridge_shape_b.V2DeploymentBridgeShapeBTests.test_fnd_bridge_routes_call_cataloged_v2_entrypoints) ... ok
test_health_does_not_expose_configured_paths (test_v2_deployment_bridge_shape_b.V2DeploymentBridgeShapeBTests.test_health_does_not_expose_configured_paths) ... ok
test_tff_bridge_mount_uses_the_same_v2_shell_entrypoint (test_v2_deployment_bridge_shape_b.V2DeploymentBridgeShapeBTests.test_tff_bridge_mount_uses_the_same_v2_shell_entrypoint) ... ok
test_admin_shell_aws_and_datum_routes_call_v2_runtime_directly (test_v2_native_portal_host.V2NativePortalHostTests.test_admin_shell_aws_and_datum_routes_call_v2_runtime_directly) ... ok
test_analytics_collect_writes_only_to_clients_domain_path (test_v2_native_portal_host.V2NativePortalHostTests.test_analytics_collect_writes_only_to_clients_domain_path) ... ok
test_non_live_aws_mapping_fails_closed_for_health_and_aws_routes (test_v2_native_portal_host.V2NativePortalHostTests.test_non_live_aws_mapping_fails_closed_for_health_and_aws_routes) ... ok
test_portal_and_health_are_native_v2_without_admin_bridge_route (test_v2_native_portal_host.V2NativePortalHostTests.test_portal_and_health_are_native_v2_without_admin_bridge_route) ... ok
test_portal_static_css_and_shell_markup (test_v2_native_portal_host.V2NativePortalHostTests.test_portal_static_css_and_shell_markup) ... ok
test_url_deep_linking_bootstraps_to_correct_slice (test_v2_native_portal_host.V2NativePortalHostTests.test_url_deep_linking_bootstraps_to_correct_slice) ... ok

----------------------------------------------------------------------
Ran 29 tests in 1.441s

OK
== MyCiteV2/tests/unit ==
test_descriptor_rejects_writable_tool_without_audit_or_read_after_write (test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_descriptor_rejects_writable_tool_without_audit_or_read_after_write) ... ok
test_runtime_entrypoint_catalog_is_static_and_serializable (test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_runtime_entrypoint_catalog_is_static_and_serializable) ... ok
test_shared_runtime_envelope_shape_is_fixed (test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_shared_runtime_envelope_shape_is_fixed) ... ok
test_tool_descriptors_have_stable_drop_in_shape (test_admin_tool_platform_contract.AdminToolPlatformContractTests.test_tool_descriptors_have_stable_drop_in_shape) ... ok
test_command_normalizes_focus_subject_and_selected_verified_sender (test_aws_narrow_write.AwsNarrowWriteTests.test_command_normalizes_focus_subject_and_selected_verified_sender) ... ok
test_command_rejects_unapproved_fields (test_aws_narrow_write.AwsNarrowWriteTests.test_command_rejects_unapproved_fields) ... ok
test_service_applies_write_and_prepares_local_audit_payload (test_aws_narrow_write.AwsNarrowWriteTests.test_service_applies_write_and_prepares_local_audit_payload) ... ok
test_normalization_derives_compatibility_warning_and_safe_summary (test_aws_operational_visibility.AwsOperationalVisibilityTests.test_normalization_derives_compatibility_warning_and_safe_summary) ... ok
test_secondary_send_domain_must_cover_selected_sender (test_aws_operational_visibility.AwsOperationalVisibilityTests.test_secondary_send_domain_must_cover_selected_sender) ... ok
test_secret_bearing_keys_and_sender_mismatch_are_rejected (test_aws_operational_visibility.AwsOperationalVisibilityTests.test_secret_bearing_keys_and_sender_mismatch_are_rejected) ... ok
test_service_reads_through_port_and_returns_none_when_missing (test_aws_operational_visibility.AwsOperationalVisibilityTests.test_service_reads_through_port_and_returns_none_when_missing) ... ok
test_normalization_is_deterministic (test_datum_refs.DatumRefUnitTests.test_normalization_is_deterministic) ... ok
test_normalize_can_emit_canonical_forms_needed_by_mvp (test_datum_refs.DatumRefUnitTests.test_normalize_can_emit_canonical_forms_needed_by_mvp) ... ok
test_normalize_rejects_missing_or_invalid_qualification_requirements (test_datum_refs.DatumRefUnitTests.test_normalize_rejects_missing_or_invalid_qualification_requirements) ... ok
test_normalize_rejects_unknown_write_format (test_datum_refs.DatumRefUnitTests.test_normalize_rejects_unknown_write_format) ... ok
test_parse_accepts_local_dot_and_hyphen_forms (test_datum_refs.DatumRefUnitTests.test_parse_accepts_local_dot_and_hyphen_forms) ... ok
test_parse_rejects_malformed_datum_refs (test_datum_refs.DatumRefUnitTests.test_parse_rejects_malformed_datum_refs) ... ok
test_append_handoff_uses_normalized_port_payload (test_local_audit.LocalAuditUnitTests.test_append_handoff_uses_normalized_port_payload) ... ok
test_local_audit_record_normalizes_subject_and_text_fields (test_local_audit.LocalAuditUnitTests.test_local_audit_record_normalizes_subject_and_text_fields) ... ok
test_local_audit_rejects_forbidden_and_unsupported_keys (test_local_audit.LocalAuditUnitTests.test_local_audit_rejects_forbidden_and_unsupported_keys) ... ok
test_read_by_id_handoff_returns_semantic_record (test_local_audit.LocalAuditUnitTests.test_read_by_id_handoff_returns_semantic_record) ... ok
test_read_by_id_returns_none_when_not_found (test_local_audit.LocalAuditUnitTests.test_read_by_id_returns_none_when_not_found) ... ok
test_band_name_is_fixed_for_admin_band0 (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_band_name_is_fixed_for_admin_band0) ... ok
test_catalog_and_registry_are_serializable_and_shell_owned (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_catalog_and_registry_are_serializable_and_shell_owned) ... ok
test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_launch_decision_is_shell_owned_and_approved_for_trusted_tenant) ... ok
test_non_internal_audience_is_denied_for_admin_band0 (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_non_internal_audience_is_denied_for_admin_band0) ... ok
test_request_contract_rejects_invalid_schema_and_audience (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_request_contract_rejects_invalid_schema_and_audience) ... ok
test_request_defaults_to_internal_home_status (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_request_defaults_to_internal_home_status) ... ok
test_shell_chrome_round_trips_in_request_dict (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_shell_chrome_round_trips_in_request_dict) ... ok
test_shell_entry_alias_resolves_to_home_status (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_shell_entry_alias_resolves_to_home_status) ... ok
test_tool_registry_surface_is_available_and_aws_redirects_to_registry (test_state_machine_admin_shell.AdminShellStateMachineUnitTests.test_tool_registry_surface_is_available_and_aws_redirects_to_registry) ... ok
test_aitas_context_serializes_only_attention_and_intention (test_state_machine_hanus_shell.HanusShellUnitTests.test_aitas_context_serializes_only_attention_and_intention) ... ok
test_contract_shapes_round_trip_through_serializable_payloads (test_state_machine_hanus_shell.HanusShellUnitTests.test_contract_shapes_round_trip_through_serializable_payloads) ... ok
test_reducer_is_deterministic_for_identical_input (test_state_machine_hanus_shell.HanusShellUnitTests.test_reducer_is_deterministic_for_identical_input) ... ok
test_reducer_produces_normalized_state_and_shell_result (test_state_machine_hanus_shell.HanusShellUnitTests.test_reducer_produces_normalized_state_and_shell_result) ... ok
test_shell_action_normalizes_focus_subject_to_canonical_dot (test_state_machine_hanus_shell.HanusShellUnitTests.test_shell_action_normalizes_focus_subject_to_canonical_dot) ... ok
test_shell_action_rejects_non_contract_or_noncanonical_input (test_state_machine_hanus_shell.HanusShellUnitTests.test_shell_action_rejects_non_contract_or_noncanonical_input) ... ok

----------------------------------------------------------------------
Ran 37 tests in 0.005s

OK
```

### 5.2 Step 2 — full `verify_v2_portal_deploy_truth.sh` transcript

```text
== repo: portal.html markers ==
== repo: v2_portal_shell.js present ==
repo template/static checks: OK
== repo: srv-infra nginx intent file readable ==
repo nginx intent file: OK
== live: HTTPS static + healthz (edge, no portal session required) ==
live static + healthz: OK
== live: portal HTML (markers) ==
WARN: edge /portal/system HTTP 200 but body is not V2 portal shell (typical: oauth2 sign-in HTML without session)
using auto-selected loopback http://127.0.0.1:6101 for HTML markers
checked HTML markers via loopback http://127.0.0.1:6101/portal/system
portal HTML markers: OK
== on-host: systemd mycite-v2-fnd-portal.service ==
● mycite-v2-fnd-portal.service - MyCite V2 Fruitful Network Development portal
     Loaded: loaded (/etc/systemd/system/mycite-v2-fnd-portal.service; enabled; preset: enabled)
    Drop-In: /etc/systemd/system/mycite-v2-fnd-portal.service.d
             └─override.conf
     Active: active (running) since Sat 2026-04-11 00:45:09 UTC; 3h 31min ago
 Invocation: c589398e81a54203b3935e49b8120179
   Main PID: 48181 (gunicorn)
      Tasks: 4 (limit: 1126)
     Memory: 28.2M (peak: 58.4M, swap: 42.1M, swap peak: 42.3M)
        CPU: 2.216s
     CGroup: /system.slice/mycite-v2-fnd-portal.service
             ├─48181 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app
             ├─48184 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app
             └─48186 /srv/venvs/fnd_portal/bin/python3 /srv/venvs/fnd_portal/bin/gunicorn --workers 2 --bind 127.0.0.1:6101 MyCiteV2.instances._shared.portal_host.app:app

Apr 11 00:45:09 ip-172-31-21-63 systemd[1]: Started mycite-v2-fnd-portal.service - MyCite V2 Fruitful Network Development portal.
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Starting gunicorn 25.3.0
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Listening at: http://127.0.0.1:6101 (48181)
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Using worker: sync
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48184]: [2026-04-11 00:45:09 +0000] [48184] [INFO] Booting worker with pid: 48184
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48186]: [2026-04-11 00:45:09 +0000] [48186] [INFO] Booting worker with pid: 48186
Apr 11 00:45:09 ip-172-31-21-63 gunicorn[48181]: [2026-04-11 00:45:09 +0000] [48181] [INFO] Control socket listening at /home/admin/.gunicorn/gunicorn.ctl
systemd ActiveState=active SubState=running FragmentPath=/etc/systemd/system/mycite-v2-fnd-portal.service
systemd: OK
== on-host: nginx effective config (semantic grep vs repo intent) ==
nginx effective vs intent (grep-level): OK

All deploy-truth checks passed.
```

---

## 6. Acceptance mapping

| Acceptance criterion | Evidence | Result |
|----------------------|----------|--------|
| Repo test command for portal host documented and stable | **`reports/T-006-smoke-gate.md`** Step 1 + task **`execution.repo_test_command`**; §5.1 all dirs **OK**, exit 0 | pass |
| Live smoke command set documented and stable | Smoke gate Step 2 + task **`execution.live_check_command`**; §5.2 success line | pass |
| Gate checks shell markers, static assets, health static bundle | Smoke gate table + script stages (**repo template/static**, **live static + healthz**, **portal HTML markers**); includes **`portal_static_bundle`** / health schema via script | pass |
| Verifier can run gate without prompt history | Commands fully specified in YAML + smoke doc; this report is independent | pass |
| Failure in repo tests or live smoke blocks closure | Smoke doc §Failure semantics; both legs passed here | pass |

---

## 7. Repo / host / live mismatches

None. Step 2 **WARN** on edge **`/portal/system`** is expected (OAuth HTML); script validates shell markers on loopback and still reports **`portal HTML markers: OK`**.

---

## 8. Final verdict

**Verdict (required):** `PASS`

Independent Step 1 and Step 2 both exited **0** with transcripts above; smoke gate doc satisfies **`artifacts.smoke_gate_doc`** and **`closure_rule`** evidence needs.

---

## 9. Recommended next status

`status: verified_pass`  
`verification_result: pass`  
`execution.current_role: lead`  
`execution.next_role: lead`
