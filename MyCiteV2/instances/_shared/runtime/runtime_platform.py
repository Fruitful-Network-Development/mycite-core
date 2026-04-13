from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_BAND1_AWS_NAME,
    ADMIN_BAND2_AWS_NAME,
    ADMIN_BAND3_AWS_SANDBOX_NAME,
    ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
    ADMIN_BAND5_CTS_GIS_NAME,
    ADMIN_ENTRYPOINT_ID,
    ADMIN_EXPOSURE_INTERNAL_ONLY,
    ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
    ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
    ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
    ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_TOOL_KIND_GENERAL,
    ADMIN_TOOL_KIND_HOST_ALIAS,
    ADMIN_TOOL_KIND_SERVICE,
    ADMIN_TOOL_LAUNCH_CONTRACT,
    ADMIN_TOOL_SURFACE_BOUNDED_WRITE,
    ADMIN_TOOL_SURFACE_READ_ONLY,
    AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
    AWS_CSM_ONBOARDING_SLICE_ID,
    AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
    AWS_CSM_SANDBOX_SLICE_ID,
    CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
    CTS_GIS_READ_ONLY_SLICE_ID,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
)
from MyCiteV2.packages.state_machine.trusted_tenant_portal import (
    BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
    BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
    TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
)

ADMIN_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.admin.runtime.envelope.v1"
ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA = "mycite.v2.admin.runtime_entrypoint_descriptor.v1"
ADMIN_HOME_STATUS_SURFACE_SCHEMA = "mycite.v2.admin.home_status.surface.v1"
ADMIN_NETWORK_ROOT_SURFACE_SCHEMA = "mycite.v2.admin.network_root.surface.v1"
ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA = "mycite.v2.admin.tool_registry.surface.v1"
ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE = "tool_not_exposed"
ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA = "mycite.v2.admin.aws_csm.family_home.request.v1"
ADMIN_AWS_CSM_FAMILY_HOME_SURFACE_SCHEMA = "mycite.v2.admin.aws_csm.family_home.surface.v1"
ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA = "mycite.v2.admin.aws_csm.newsletter.request.v1"
ADMIN_AWS_CSM_NEWSLETTER_SURFACE_SCHEMA = "mycite.v2.admin.aws_csm.newsletter.surface.v1"
ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.aws.read_only.request.v1"
ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA = "mycite.v2.admin.aws.read_only.surface.v1"
ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA = "mycite.v2.admin.aws.narrow_write.request.v1"
ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA = "mycite.v2.admin.aws.narrow_write.surface.v1"
ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA = "mycite.v2.admin.aws.csm_onboarding.request.v1"
ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA = "mycite.v2.admin.aws.csm_onboarding.surface.v1"
ADMIN_CTS_GIS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.cts_gis.read_only.request.v1"
ADMIN_CTS_GIS_READ_ONLY_SURFACE_SCHEMA = "mycite.v2.admin.cts_gis.read_only.surface.v1"
TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.portal.runtime.envelope.v1"
TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA = "mycite.v2.portal.runtime_entrypoint_descriptor.v1"
TRUSTED_TENANT_HOME_SURFACE_SCHEMA = "mycite.v2.portal.home_tenant_status.surface.v1"
TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA = "mycite.v2.portal.operational_status.request.v1"
TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA = "mycite.v2.portal.operational_status.surface.v1"
TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA = "mycite.v2.portal.audit_activity.request.v1"
TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA = "mycite.v2.portal.audit_activity.surface.v1"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA = "mycite.v2.portal.profile_basics_write.request.v1"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_SURFACE_SCHEMA = "mycite.v2.portal.profile_basics_write.surface.v1"
TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID = "portal.home.tenant_status"
TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID = "portal.operational_status"
TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID = "portal.audit_activity"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID = "portal.profile_basics_write"
BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID = "band1.operational_status_surface"
BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID = "band1.audit_activity_visibility"
BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID = "band2.profile_basics_write_surface"
BAND2_TRUSTED_TENANT_WRITABLE_NAME = "Band 2 Trusted-Tenant Writable Slice"
TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS = "trusted-tenant-writable"

AWS_NARROW_WRITE_RECOVERY_REFERENCE = (
    "docs/plans/post_mvp_rollout/admin_first/aws_narrow_write_recovery.md"
)
AWS_CSM_ONBOARDING_RECOVERY_REFERENCE = (
    "docs/plans/post_mvp_rollout/post_aws_tool_platform/read_only_and_bounded_write_patterns.md"
)
PROFILE_BASICS_WRITE_RECOVERY_REFERENCE = (
    "docs/plans/post_mvp_rollout/profile_basics_write_recovery.md"
)

ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT = "admin-shell-entry"
ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS = (
    "schema",
    "admin_band",
    "exposure_status",
    "tenant_scope",
    "requested_slice_id",
    "slice_id",
    "entrypoint_id",
    "read_write_posture",
    "shell_state",
    "surface_payload",
    "shell_composition",
    "warnings",
    "error",
)
TRUSTED_TENANT_RUNTIME_REQUIRED_ENVELOPE_KEYS = (
    "schema",
    "rollout_band",
    "exposure_status",
    "tenant_scope",
    "requested_slice_id",
    "slice_id",
    "entrypoint_id",
    "read_write_posture",
    "shell_state",
    "surface_payload",
    "shell_composition",
    "warnings",
    "error",
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_admin_runtime_tool_kind(value: object, *, required: bool) -> str | None:
    tool_kind = _as_text(value).lower()
    if not tool_kind:
        if required:
            raise ValueError("runtime_entrypoint.tool_kind is required for shell-owned tool entrypoints")
        return None
    if tool_kind not in {ADMIN_TOOL_KIND_GENERAL, ADMIN_TOOL_KIND_SERVICE, ADMIN_TOOL_KIND_HOST_ALIAS}:
        raise ValueError(
            "runtime_entrypoint.tool_kind must be one of: "
            f"{ADMIN_TOOL_KIND_GENERAL}, {ADMIN_TOOL_KIND_SERVICE}, {ADMIN_TOOL_KIND_HOST_ALIAS}; default_tool is forbidden"
        )
    return tool_kind


def _normalize_shared_portal_capabilities(value: object) -> tuple[str, ...]:
    if value in {None, ""}:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("runtime_entrypoint.shared_portal_capabilities must be a list, tuple, or null")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        capability = _as_text(item).lower().replace("-", "_").replace(" ", "_")
        if not capability or capability in seen:
            continue
        normalized.append(capability)
        seen.add(capability)
    return tuple(normalized)


def _normalize_known_tool_ids(known_tool_ids: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in known_tool_ids:
        tool_id = _as_text(value)
        if not tool_id or tool_id in seen:
            continue
        normalized.append(tool_id)
        seen.add(tool_id)
    return normalized


def build_allow_all_admin_tool_exposure_policy(
    *,
    known_tool_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    normalized_known = _normalize_known_tool_ids(known_tool_ids)
    return {
        "known_tool_ids": list(normalized_known),
        "configured_tool_ids": list(normalized_known),
        "enabled_tool_ids": list(normalized_known),
        "disabled_tool_ids": [],
        "missing_tool_ids": [],
        "unknown_tool_ids": [],
        "invalid_tool_ids": [],
        "configured_tools": {tool_id: True for tool_id in normalized_known},
        "policy_source": "runtime_default_allow_all",
    }


def build_admin_tool_exposure_policy(
    raw_policy: object,
    *,
    known_tool_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    normalized_known = _normalize_known_tool_ids(known_tool_ids)
    known_set = set(normalized_known)
    configured_tools: dict[str, bool] = {}
    unknown_tool_ids: list[str] = []
    invalid_tool_ids: list[str] = []

    if not isinstance(raw_policy, dict):
        raw_policy = {}

    for raw_tool_id, raw_entry in raw_policy.items():
        tool_id = _as_text(raw_tool_id)
        if not tool_id:
            continue
        if tool_id not in known_set:
            unknown_tool_ids.append(tool_id)
            continue
        enabled_value: object | None
        if isinstance(raw_entry, dict):
            enabled_value = raw_entry.get("enabled")
        elif isinstance(raw_entry, bool):
            enabled_value = raw_entry
        else:
            enabled_value = None
        if not isinstance(enabled_value, bool):
            invalid_tool_ids.append(tool_id)
            continue
        configured_tools[tool_id] = enabled_value

    configured_tool_ids = [tool_id for tool_id in normalized_known if tool_id in configured_tools]
    enabled_tool_ids = [tool_id for tool_id in normalized_known if configured_tools.get(tool_id) is True]
    missing_tool_ids = [tool_id for tool_id in normalized_known if tool_id not in configured_tools]
    disabled_tool_ids = [tool_id for tool_id in normalized_known if configured_tools.get(tool_id) is not True]

    return {
        "known_tool_ids": list(normalized_known),
        "configured_tool_ids": list(configured_tool_ids),
        "enabled_tool_ids": list(enabled_tool_ids),
        "disabled_tool_ids": list(disabled_tool_ids),
        "missing_tool_ids": list(missing_tool_ids),
        "unknown_tool_ids": list(unknown_tool_ids),
        "invalid_tool_ids": list(invalid_tool_ids),
        "configured_tools": dict(configured_tools),
        "policy_source": "private_config_json",
    }


def admin_tool_exposure_config_enabled(
    tool_exposure_policy: dict[str, Any] | None,
    *,
    tool_id: str,
) -> bool:
    if tool_exposure_policy is None:
        return True
    configured_tools = tool_exposure_policy.get("configured_tools")
    if not isinstance(configured_tools, dict):
        return False
    return configured_tools.get(_as_text(tool_id)) is True


@dataclass(frozen=True)
class AdminRuntimeEntrypointDescriptor:
    entrypoint_id: str
    callable_path: str
    slice_id: str
    admin_band: str
    exposure_status: str
    read_write_posture: str
    launch_contract: str
    surface_pattern: str
    surface_schema: str
    tool_kind: str | None = None
    shared_portal_capabilities: tuple[str, ...] = ()
    required_configuration: tuple[str, ...] = ()
    schema: str = field(default=ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not _as_text(self.entrypoint_id):
            raise ValueError("runtime_entrypoint.entrypoint_id is required")
        if not _as_text(self.callable_path):
            raise ValueError("runtime_entrypoint.callable_path is required")
        if not _as_text(self.slice_id):
            raise ValueError("runtime_entrypoint.slice_id is required")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("runtime_entrypoint.read_write_posture must be read-only or write")
        if self.launch_contract not in {ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT, ADMIN_TOOL_LAUNCH_CONTRACT}:
            raise ValueError("runtime_entrypoint.launch_contract is invalid")
        if self.surface_pattern not in {"admin-shell", ADMIN_TOOL_SURFACE_READ_ONLY, ADMIN_TOOL_SURFACE_BOUNDED_WRITE}:
            raise ValueError("runtime_entrypoint.surface_pattern is invalid")
        required_tool_kind = self.launch_contract == ADMIN_TOOL_LAUNCH_CONTRACT
        object.__setattr__(
            self,
            "tool_kind",
            _normalize_admin_runtime_tool_kind(self.tool_kind, required=required_tool_kind),
        )
        object.__setattr__(
            self,
            "shared_portal_capabilities",
            _normalize_shared_portal_capabilities(self.shared_portal_capabilities),
        )
        if self.launch_contract == ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT and self.tool_kind is not None:
            raise ValueError("runtime_entrypoint.tool_kind must be null for root-service shell entrypoints")
        if self.read_write_posture == "write" and self.surface_pattern != ADMIN_TOOL_SURFACE_BOUNDED_WRITE:
            raise ValueError("write runtime entrypoints must use the bounded-write surface pattern")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "entrypoint_id": self.entrypoint_id,
            "callable_path": self.callable_path,
            "slice_id": self.slice_id,
            "admin_band": self.admin_band,
            "exposure_status": self.exposure_status,
            "read_write_posture": self.read_write_posture,
            "launch_contract": self.launch_contract,
            "surface_pattern": self.surface_pattern,
            "surface_schema": self.surface_schema,
            "tool_kind": self.tool_kind,
            "shared_portal_capabilities": list(self.shared_portal_capabilities),
            "required_configuration": list(self.required_configuration),
        }


@dataclass(frozen=True)
class TrustedTenantRuntimeEntrypointDescriptor:
    entrypoint_id: str
    callable_path: str
    slice_id: str
    rollout_band: str
    exposure_status: str
    read_write_posture: str
    launch_contract: str
    surface_pattern: str
    surface_schema: str
    required_configuration: tuple[str, ...] = ()
    schema: str = field(default=TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not _as_text(self.entrypoint_id):
            raise ValueError("trusted_tenant_runtime_entrypoint.entrypoint_id is required")
        if not _as_text(self.callable_path):
            raise ValueError("trusted_tenant_runtime_entrypoint.callable_path is required")
        if not _as_text(self.slice_id):
            raise ValueError("trusted_tenant_runtime_entrypoint.slice_id is required")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError(
                "trusted_tenant_runtime_entrypoint.read_write_posture must be read-only or write"
            )
        if self.launch_contract != ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT:
            raise ValueError("trusted_tenant_runtime_entrypoint.launch_contract is invalid")
        if self.surface_pattern not in {
            "tenant-home",
            "tenant-operational-status",
            "tenant-audit-activity",
            "tenant-profile-basics-write",
        }:
            raise ValueError("trusted_tenant_runtime_entrypoint.surface_pattern is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "entrypoint_id": self.entrypoint_id,
            "callable_path": self.callable_path,
            "slice_id": self.slice_id,
            "rollout_band": self.rollout_band,
            "exposure_status": self.exposure_status,
            "read_write_posture": self.read_write_posture,
            "launch_contract": self.launch_contract,
            "surface_pattern": self.surface_pattern,
            "surface_schema": self.surface_schema,
            "required_configuration": list(self.required_configuration),
        }


def build_admin_runtime_entrypoint_catalog() -> tuple[AdminRuntimeEntrypointDescriptor, ...]:
    return (
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=ADMIN_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_runtime.run_admin_shell_entry",
            slice_id=ADMIN_HOME_STATUS_SLICE_ID,
            admin_band=ADMIN_BAND0_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
            read_write_posture="read-only",
            launch_contract=ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT,
            surface_pattern="admin-shell",
            surface_schema=ADMIN_HOME_STATUS_SURFACE_SCHEMA,
            required_configuration=("audit_storage_file_optional",),
        ),
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=AWS_CSM_FAMILY_HOME_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_aws_runtime.run_admin_aws_csm_family_home",
            slice_id=AWS_READ_ONLY_SLICE_ID,
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            read_write_posture="read-only",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_READ_ONLY,
            surface_schema=ADMIN_AWS_CSM_FAMILY_HOME_SURFACE_SCHEMA,
            tool_kind=ADMIN_TOOL_KIND_SERVICE,
            shared_portal_capabilities=("external_service_binding",),
            required_configuration=("aws_status_file", "private_dir"),
        ),
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_aws_runtime.run_admin_aws_read_only",
            slice_id=AWS_READ_ONLY_SLICE_ID,
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            read_write_posture="read-only",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_READ_ONLY,
            surface_schema=ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
            tool_kind=ADMIN_TOOL_KIND_SERVICE,
            shared_portal_capabilities=("external_service_binding",),
            required_configuration=("aws_status_file",),
        ),
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_aws_runtime.run_admin_aws_narrow_write",
            slice_id=AWS_NARROW_WRITE_SLICE_ID,
            admin_band=ADMIN_BAND2_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
            read_write_posture="write",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_BOUNDED_WRITE,
            surface_schema=ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA,
            tool_kind=ADMIN_TOOL_KIND_SERVICE,
            shared_portal_capabilities=("external_service_binding",),
            required_configuration=("aws_status_file", "audit_storage_file"),
        ),
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=AWS_CSM_SANDBOX_READ_ONLY_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_aws_runtime.run_admin_aws_csm_sandbox_read_only",
            slice_id=AWS_CSM_SANDBOX_SLICE_ID,
            admin_band=ADMIN_BAND3_AWS_SANDBOX_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_SANDBOX_READ_ONLY,
            read_write_posture="read-only",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_READ_ONLY,
            surface_schema=ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
            tool_kind=ADMIN_TOOL_KIND_SERVICE,
            shared_portal_capabilities=("external_service_binding", "sandbox_projection"),
            required_configuration=("aws_csm_sandbox_status_file",),
        ),
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=AWS_CSM_ONBOARDING_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_aws_runtime.run_admin_aws_csm_onboarding",
            slice_id=AWS_CSM_ONBOARDING_SLICE_ID,
            admin_band=ADMIN_BAND4_AWS_CSM_ONBOARDING_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_CSM_ONBOARDING,
            read_write_posture="write",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_BOUNDED_WRITE,
            surface_schema=ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA,
            tool_kind=ADMIN_TOOL_KIND_SERVICE,
            shared_portal_capabilities=("external_service_binding",),
            required_configuration=("aws_status_file", "audit_storage_file"),
        ),
        AdminRuntimeEntrypointDescriptor(
            entrypoint_id=CTS_GIS_READ_ONLY_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_cts_gis_runtime.run_admin_cts_gis_read_only",
            slice_id=CTS_GIS_READ_ONLY_SLICE_ID,
            admin_band=ADMIN_BAND5_CTS_GIS_NAME,
            exposure_status=ADMIN_EXPOSURE_INTERNAL_ONLY,
            read_write_posture="read-only",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_READ_ONLY,
            surface_schema=ADMIN_CTS_GIS_READ_ONLY_SURFACE_SCHEMA,
            tool_kind=ADMIN_TOOL_KIND_GENERAL,
            shared_portal_capabilities=("datum_recognition", "spatial_projection"),
            required_configuration=("data_dir",),
        ),
    )


def resolve_admin_runtime_entrypoint(entrypoint_id: object) -> AdminRuntimeEntrypointDescriptor | None:
    normalized_entrypoint_id = _as_text(entrypoint_id)
    for descriptor in build_admin_runtime_entrypoint_catalog():
        if descriptor.entrypoint_id == normalized_entrypoint_id:
            return descriptor
    return None


def build_trusted_tenant_runtime_entrypoint_catalog() -> tuple[TrustedTenantRuntimeEntrypointDescriptor, ...]:
    return (
        TrustedTenantRuntimeEntrypointDescriptor(
            entrypoint_id=TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.tenant_portal_runtime.run_trusted_tenant_portal_home",
            slice_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
            exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
            read_write_posture="read-only",
            launch_contract=ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT,
            surface_pattern="tenant-home",
            surface_schema=TRUSTED_TENANT_HOME_SURFACE_SCHEMA,
            required_configuration=("data_dir", "public_dir", "tenant_domain"),
        ),
        TrustedTenantRuntimeEntrypointDescriptor(
            entrypoint_id=TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
            callable_path=(
                "MyCiteV2.instances._shared.runtime.tenant_operational_status_runtime."
                "run_trusted_tenant_operational_status"
            ),
            slice_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
            rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
            exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
            read_write_posture="read-only",
            launch_contract=ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT,
            surface_pattern="tenant-operational-status",
            surface_schema=TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA,
            required_configuration=("audit_storage_file",),
        ),
        TrustedTenantRuntimeEntrypointDescriptor(
            entrypoint_id=TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
            callable_path=(
                "MyCiteV2.instances._shared.runtime.tenant_audit_activity_runtime."
                "run_trusted_tenant_audit_activity"
            ),
            slice_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
            rollout_band=BAND1_TRUSTED_TENANT_READ_ONLY_NAME,
            exposure_status=TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS,
            read_write_posture="read-only",
            launch_contract=ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT,
            surface_pattern="tenant-audit-activity",
            surface_schema=TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA,
            required_configuration=("audit_storage_file",),
        ),
        TrustedTenantRuntimeEntrypointDescriptor(
            entrypoint_id=TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID,
            callable_path=(
                "MyCiteV2.instances._shared.runtime.tenant_profile_basics_write_runtime."
                "run_trusted_tenant_profile_basics_write"
            ),
            slice_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
            rollout_band=BAND2_TRUSTED_TENANT_WRITABLE_NAME,
            exposure_status=TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS,
            read_write_posture="write",
            launch_contract=ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT,
            surface_pattern="tenant-profile-basics-write",
            surface_schema=TRUSTED_TENANT_PROFILE_BASICS_WRITE_SURFACE_SCHEMA,
            required_configuration=("data_dir", "public_dir", "tenant_domain", "audit_storage_file"),
        ),
    )


def resolve_trusted_tenant_runtime_entrypoint(
    entrypoint_id: object,
) -> TrustedTenantRuntimeEntrypointDescriptor | None:
    normalized_entrypoint_id = _as_text(entrypoint_id)
    for descriptor in build_trusted_tenant_runtime_entrypoint_catalog():
        if descriptor.entrypoint_id == normalized_entrypoint_id:
            return descriptor
    return None


def build_admin_runtime_error(*, code: str, message: str) -> dict[str, str]:
    return {
        "code": _as_text(code),
        "message": _as_text(message),
    }


def build_admin_runtime_envelope(
    *,
    admin_band: str,
    exposure_status: str,
    tenant_scope: dict[str, Any],
    requested_slice_id: str,
    slice_id: str,
    entrypoint_id: str,
    read_write_posture: str,
    shell_state: dict[str, Any],
    surface_payload: dict[str, Any] | None,
    shell_composition: dict[str, Any] | None = None,
    warnings: list[str] | tuple[str, ...] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if read_write_posture not in {"read-only", "write"}:
        raise ValueError("admin runtime envelope read_write_posture must be read-only or write")
    return {
        "schema": ADMIN_RUNTIME_ENVELOPE_SCHEMA,
        "admin_band": admin_band,
        "exposure_status": exposure_status,
        "tenant_scope": dict(tenant_scope),
        "requested_slice_id": requested_slice_id,
        "slice_id": slice_id,
        "entrypoint_id": entrypoint_id,
        "read_write_posture": read_write_posture,
        "shell_state": dict(shell_state),
        "surface_payload": surface_payload,
        "shell_composition": shell_composition,
        "warnings": list(warnings or []),
        "error": error,
    }


def build_trusted_tenant_runtime_error(*, code: str, message: str) -> dict[str, str]:
    return {
        "code": _as_text(code),
        "message": _as_text(message),
    }


def build_trusted_tenant_runtime_envelope(
    *,
    rollout_band: str,
    exposure_status: str,
    tenant_scope: dict[str, Any],
    requested_slice_id: str,
    slice_id: str,
    entrypoint_id: str,
    read_write_posture: str,
    shell_state: dict[str, Any],
    surface_payload: dict[str, Any] | None,
    shell_composition: dict[str, Any] | None = None,
    warnings: list[str] | tuple[str, ...] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if read_write_posture not in {"read-only", "write"}:
        raise ValueError(
            "trusted tenant runtime envelope read_write_posture must be read-only or write"
        )
    return {
        "schema": TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA,
        "rollout_band": rollout_band,
        "exposure_status": exposure_status,
        "tenant_scope": dict(tenant_scope),
        "requested_slice_id": requested_slice_id,
        "slice_id": slice_id,
        "entrypoint_id": entrypoint_id,
        "read_write_posture": read_write_posture,
        "shell_state": dict(shell_state),
        "surface_payload": surface_payload,
        "shell_composition": shell_composition,
        "warnings": list(warnings or []),
        "error": error,
    }


__all__ = [
    "ADMIN_AWS_CSM_ONBOARDING_REQUEST_SCHEMA",
    "ADMIN_AWS_CSM_ONBOARDING_SURFACE_SCHEMA",
    "ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA",
    "ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA",
    "ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA",
    "ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA",
    "ADMIN_HOME_STATUS_SURFACE_SCHEMA",
    "ADMIN_NETWORK_ROOT_SURFACE_SCHEMA",
    "ADMIN_RUNTIME_ENVELOPE_SCHEMA",
    "ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA",
    "ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS",
    "ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT",
    "ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA",
    "AWS_CSM_ONBOARDING_RECOVERY_REFERENCE",
    "AWS_NARROW_WRITE_RECOVERY_REFERENCE",
    "BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID",
    "BAND2_TRUSTED_TENANT_WRITABLE_NAME",
    "AdminRuntimeEntrypointDescriptor",
    "PROFILE_BASICS_WRITE_RECOVERY_REFERENCE",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_SURFACE_SCHEMA",
    "build_admin_runtime_entrypoint_catalog",
    "build_admin_runtime_envelope",
    "build_admin_runtime_error",
    "build_trusted_tenant_runtime_envelope",
    "build_trusted_tenant_runtime_entrypoint_catalog",
    "build_trusted_tenant_runtime_error",
    "resolve_admin_runtime_entrypoint",
    "resolve_trusted_tenant_runtime_entrypoint",
    "BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID",
    "BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_SURFACE_SCHEMA",
    "TRUSTED_TENANT_HOME_SURFACE_SCHEMA",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_SURFACE_SCHEMA",
    "TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID",
    "TRUSTED_TENANT_RUNTIME_ENVELOPE_SCHEMA",
    "TRUSTED_TENANT_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA",
    "TRUSTED_TENANT_RUNTIME_REQUIRED_ENVELOPE_KEYS",
    "TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS",
    "TrustedTenantRuntimeEntrypointDescriptor",
]
