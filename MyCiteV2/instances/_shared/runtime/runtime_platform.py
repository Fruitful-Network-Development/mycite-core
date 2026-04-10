from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from MyCiteV2.packages.state_machine.hanus_shell import (
    ADMIN_BAND0_NAME,
    ADMIN_BAND1_AWS_NAME,
    ADMIN_BAND2_AWS_NAME,
    ADMIN_ENTRYPOINT_ID,
    ADMIN_EXPOSURE_INTERNAL_ONLY,
    ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE,
    ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
    ADMIN_HOME_STATUS_SLICE_ID,
    ADMIN_TOOL_LAUNCH_CONTRACT,
    ADMIN_TOOL_SURFACE_BOUNDED_WRITE,
    ADMIN_TOOL_SURFACE_READ_ONLY,
    AWS_NARROW_WRITE_ENTRYPOINT_ID,
    AWS_NARROW_WRITE_SLICE_ID,
    AWS_READ_ONLY_ENTRYPOINT_ID,
    AWS_READ_ONLY_SLICE_ID,
)

ADMIN_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.admin.runtime.envelope.v1"
ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA = "mycite.v2.admin.runtime_entrypoint_descriptor.v1"
ADMIN_HOME_STATUS_SURFACE_SCHEMA = "mycite.v2.admin.home_status.surface.v1"
ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA = "mycite.v2.admin.tool_registry.surface.v1"
ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA = "mycite.v2.admin.aws.read_only.request.v1"
ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA = "mycite.v2.admin.aws.read_only.surface.v1"
ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA = "mycite.v2.admin.aws.narrow_write.request.v1"
ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA = "mycite.v2.admin.aws.narrow_write.surface.v1"

AWS_NARROW_WRITE_RECOVERY_REFERENCE = (
    "docs/plans/post_mvp_rollout/admin_first/aws_narrow_write_recovery.md"
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


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
            entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.admin_aws_runtime.run_admin_aws_read_only",
            slice_id=AWS_READ_ONLY_SLICE_ID,
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status=ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY,
            read_write_posture="read-only",
            launch_contract=ADMIN_TOOL_LAUNCH_CONTRACT,
            surface_pattern=ADMIN_TOOL_SURFACE_READ_ONLY,
            surface_schema=ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA,
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
            required_configuration=("aws_status_file", "audit_storage_file"),
        ),
    )


def resolve_admin_runtime_entrypoint(entrypoint_id: object) -> AdminRuntimeEntrypointDescriptor | None:
    normalized_entrypoint_id = _as_text(entrypoint_id)
    for descriptor in build_admin_runtime_entrypoint_catalog():
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


__all__ = [
    "ADMIN_AWS_NARROW_WRITE_REQUEST_SCHEMA",
    "ADMIN_AWS_NARROW_WRITE_SURFACE_SCHEMA",
    "ADMIN_AWS_READ_ONLY_REQUEST_SCHEMA",
    "ADMIN_AWS_READ_ONLY_SURFACE_SCHEMA",
    "ADMIN_HOME_STATUS_SURFACE_SCHEMA",
    "ADMIN_RUNTIME_ENVELOPE_SCHEMA",
    "ADMIN_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA",
    "ADMIN_RUNTIME_REQUIRED_ENVELOPE_KEYS",
    "ADMIN_SHELL_ENTRY_LAUNCH_CONTRACT",
    "ADMIN_TOOL_REGISTRY_SURFACE_SCHEMA",
    "AWS_NARROW_WRITE_RECOVERY_REFERENCE",
    "AdminRuntimeEntrypointDescriptor",
    "build_admin_runtime_entrypoint_catalog",
    "build_admin_runtime_envelope",
    "build_admin_runtime_error",
    "resolve_admin_runtime_entrypoint",
]
