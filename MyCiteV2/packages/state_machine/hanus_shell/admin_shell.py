from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ADMIN_SHELL_REQUEST_SCHEMA = "mycite.v2.admin.shell.request.v1"
ADMIN_SHELL_STATE_SCHEMA = "mycite.v2.admin.shell.state.v1"

ADMIN_BAND0_NAME = "Admin Band 0 Internal Admin Replacement"
ADMIN_BAND1_AWS_NAME = "Admin Band 1 Trusted-Tenant AWS Read-Only"
ADMIN_BAND2_AWS_NAME = "Admin Band 2 Trusted-Tenant AWS Narrow Write"

ADMIN_EXPOSURE_INTERNAL_ONLY = "internal-only"
ADMIN_ENTRYPOINT_ID = "admin.shell_entry"

ADMIN_SHELL_ENTRY_SLICE_ID = "admin_band0.shell_entry"
ADMIN_HOME_STATUS_SLICE_ID = "admin_band0.home_status"
ADMIN_TOOL_REGISTRY_SLICE_ID = "admin_band0.tool_registry"
AWS_READ_ONLY_SLICE_ID = "admin_band1.aws_read_only_surface"
AWS_NARROW_WRITE_SLICE_ID = "admin_band2.aws_narrow_write_surface"
AWS_READ_ONLY_ENTRYPOINT_ID = "admin.aws.read_only"

INTERNAL_ADMIN_SCOPE_ID = "internal-admin"

_ALLOWED_AUDIENCES = frozenset({"internal", "trusted-tenant"})


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


@dataclass(frozen=True)
class AdminTenantScope:
    scope_id: str = INTERNAL_ADMIN_SCOPE_ID
    audience: str = "internal"

    def __post_init__(self) -> None:
        scope_id = _as_text(self.scope_id) or INTERNAL_ADMIN_SCOPE_ID
        audience = _as_text(self.audience).lower() or "internal"
        if audience not in _ALLOWED_AUDIENCES:
            supported = ", ".join(sorted(_ALLOWED_AUDIENCES))
            raise ValueError(f"admin_tenant_scope.audience must be one of: {supported}")
        object.__setattr__(self, "scope_id", scope_id)
        object.__setattr__(self, "audience", audience)

    def to_dict(self) -> dict[str, str]:
        return {
            "scope_id": self.scope_id,
            "audience": self.audience,
        }

    @classmethod
    def from_value(cls, payload: dict[str, Any] | str | None) -> "AdminTenantScope":
        if payload is None:
            return cls()
        if isinstance(payload, str):
            return cls(scope_id=payload)
        if isinstance(payload, dict):
            return cls(
                scope_id=payload.get("scope_id") or payload.get("tenant_id") or INTERNAL_ADMIN_SCOPE_ID,
                audience=payload.get("audience") or "internal",
            )
        raise ValueError("admin_tenant_scope must be a dict, string, or None")


@dataclass(frozen=True)
class AdminShellRequest:
    requested_slice_id: str = ADMIN_HOME_STATUS_SLICE_ID
    tenant_scope: AdminTenantScope = field(default_factory=AdminTenantScope)
    schema: str = field(default=ADMIN_SHELL_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        requested_slice_id = _as_text(self.requested_slice_id) or ADMIN_HOME_STATUS_SLICE_ID
        tenant_scope = self.tenant_scope if isinstance(self.tenant_scope, AdminTenantScope) else AdminTenantScope.from_value(self.tenant_scope)
        object.__setattr__(self, "requested_slice_id", requested_slice_id)
        object.__setattr__(self, "tenant_scope", tenant_scope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "requested_slice_id": self.requested_slice_id,
            "tenant_scope": self.tenant_scope.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AdminShellRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("admin_shell_request must be a dict")
        _require_schema(payload, expected=ADMIN_SHELL_REQUEST_SCHEMA, field_name="admin_shell_request.schema")
        return cls(
            requested_slice_id=payload.get("requested_slice_id") or ADMIN_HOME_STATUS_SLICE_ID,
            tenant_scope=AdminTenantScope.from_value(payload.get("tenant_scope")),
        )


@dataclass(frozen=True)
class AdminSurfaceCatalogEntry:
    slice_id: str
    label: str
    exposure_status: str
    read_write_posture: str
    status_summary: str
    surface_kind: str
    launchable: bool
    default_surface: bool = False

    def __post_init__(self) -> None:
        if not _as_text(self.slice_id):
            raise ValueError("admin_surface_catalog.slice_id is required")
        if not _as_text(self.label):
            raise ValueError("admin_surface_catalog.label is required")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("admin_surface_catalog.read_write_posture must be read-only or write")

    def to_dict(self) -> dict[str, Any]:
        return {
            "slice_id": self.slice_id,
            "label": self.label,
            "exposure_status": self.exposure_status,
            "read_write_posture": self.read_write_posture,
            "status_summary": self.status_summary,
            "surface_kind": self.surface_kind,
            "launchable": bool(self.launchable),
            "default_surface": bool(self.default_surface),
        }


@dataclass(frozen=True)
class AdminToolRegistryEntry:
    tool_id: str
    label: str
    slice_id: str
    entrypoint_id: str
    admin_band: str
    exposure_status: str
    read_write_posture: str
    status_summary: str
    audience: str
    internal_only_reason: str
    launchable: bool = False

    def __post_init__(self) -> None:
        if not _as_text(self.tool_id):
            raise ValueError("admin_tool_registry.tool_id is required")
        if not _as_text(self.label):
            raise ValueError("admin_tool_registry.label is required")
        if not _as_text(self.slice_id):
            raise ValueError("admin_tool_registry.slice_id is required")
        if not _as_text(self.entrypoint_id):
            raise ValueError("admin_tool_registry.entrypoint_id is required")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("admin_tool_registry.read_write_posture must be read-only or write")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "label": self.label,
            "slice_id": self.slice_id,
            "entrypoint_id": self.entrypoint_id,
            "admin_band": self.admin_band,
            "exposure_status": self.exposure_status,
            "read_write_posture": self.read_write_posture,
            "status_summary": self.status_summary,
            "audience": self.audience,
            "internal_only_reason": self.internal_only_reason,
            "launchable": bool(self.launchable),
        }


@dataclass(frozen=True)
class AdminShellSelection:
    requested_slice_id: str
    active_surface_id: str
    selection_status: str
    allowed: bool
    reason_code: str = ""
    reason_message: str = ""
    schema: str = field(default=ADMIN_SHELL_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        requested_slice_id = _as_text(self.requested_slice_id) or ADMIN_HOME_STATUS_SLICE_ID
        active_surface_id = _as_text(self.active_surface_id) or ADMIN_HOME_STATUS_SLICE_ID
        selection_status = _as_text(self.selection_status).lower()
        if selection_status not in {"available", "gated", "audience_denied", "unknown"}:
            raise ValueError("admin_shell_selection.selection_status is invalid")
        object.__setattr__(self, "requested_slice_id", requested_slice_id)
        object.__setattr__(self, "active_surface_id", active_surface_id)
        object.__setattr__(self, "selection_status", selection_status)
        object.__setattr__(self, "reason_code", _as_text(self.reason_code).lower())
        object.__setattr__(self, "reason_message", _as_text(self.reason_message))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "requested_slice_id": self.requested_slice_id,
            "active_surface_id": self.active_surface_id,
            "selection_status": self.selection_status,
            "allowed": bool(self.allowed),
            "reason_code": self.reason_code,
            "reason_message": self.reason_message,
        }


def build_admin_surface_catalog() -> tuple[AdminSurfaceCatalogEntry, ...]:
    return (
        AdminSurfaceCatalogEntry(
            slice_id=ADMIN_HOME_STATUS_SLICE_ID,
            label="Admin Home and Status",
            exposure_status="implemented_internal",
            read_write_posture="read-only",
            status_summary="default_landing",
            surface_kind="home_status",
            launchable=True,
            default_surface=True,
        ),
        AdminSurfaceCatalogEntry(
            slice_id=ADMIN_TOOL_REGISTRY_SLICE_ID,
            label="Tool Registry and Launcher",
            exposure_status="implemented_internal",
            read_write_posture="read-only",
            status_summary="registry_ready",
            surface_kind="tool_registry",
            launchable=True,
        ),
    )


def build_admin_tool_registry_entries() -> tuple[AdminToolRegistryEntry, ...]:
    return (
        AdminToolRegistryEntry(
            tool_id="aws",
            label="AWS Admin",
            slice_id=AWS_READ_ONLY_SLICE_ID,
            entrypoint_id=AWS_READ_ONLY_ENTRYPOINT_ID,
            admin_band=ADMIN_BAND1_AWS_NAME,
            exposure_status="planned_not_approved_for_build",
            read_write_posture="read-only",
            status_summary="planned_next",
            audience="trusted-tenant-admin",
            internal_only_reason="Admin Band 0 must remain stable before the AWS read-only slice can launch.",
            launchable=False,
        ),
    )


def resolve_admin_shell_request(request: AdminShellRequest | dict[str, Any] | None) -> AdminShellSelection:
    normalized_request = request if isinstance(request, AdminShellRequest) else AdminShellRequest.from_dict(request)

    requested_slice_id = normalized_request.requested_slice_id
    if normalized_request.tenant_scope.audience != "internal":
        return AdminShellSelection(
            requested_slice_id=requested_slice_id,
            active_surface_id=ADMIN_HOME_STATUS_SLICE_ID,
            selection_status="audience_denied",
            allowed=False,
            reason_code="audience_not_allowed",
            reason_message="Admin Band 0 is internal-only and rejects non-internal audiences.",
        )

    if requested_slice_id == ADMIN_SHELL_ENTRY_SLICE_ID:
        requested_slice_id = ADMIN_HOME_STATUS_SLICE_ID

    available_surface_ids = {entry.slice_id for entry in build_admin_surface_catalog()}
    if requested_slice_id in available_surface_ids:
        return AdminShellSelection(
            requested_slice_id=requested_slice_id,
            active_surface_id=requested_slice_id,
            selection_status="available",
            allowed=True,
        )

    for tool_entry in build_admin_tool_registry_entries():
        if requested_slice_id == tool_entry.slice_id:
            return AdminShellSelection(
                requested_slice_id=requested_slice_id,
                active_surface_id=ADMIN_HOME_STATUS_SLICE_ID,
                selection_status="gated",
                allowed=False,
                reason_code="slice_gated",
                reason_message=tool_entry.internal_only_reason,
            )

    return AdminShellSelection(
        requested_slice_id=requested_slice_id,
        active_surface_id=ADMIN_HOME_STATUS_SLICE_ID,
        selection_status="unknown",
        allowed=False,
        reason_code="slice_unknown",
        reason_message=f"Admin slice is not approved: {requested_slice_id}",
    )


__all__ = [
    "ADMIN_BAND0_NAME",
    "ADMIN_BAND1_AWS_NAME",
    "ADMIN_BAND2_AWS_NAME",
    "ADMIN_ENTRYPOINT_ID",
    "ADMIN_EXPOSURE_INTERNAL_ONLY",
    "ADMIN_HOME_STATUS_SLICE_ID",
    "ADMIN_SHELL_ENTRY_SLICE_ID",
    "ADMIN_SHELL_REQUEST_SCHEMA",
    "ADMIN_SHELL_STATE_SCHEMA",
    "ADMIN_TOOL_REGISTRY_SLICE_ID",
    "AWS_NARROW_WRITE_SLICE_ID",
    "AWS_READ_ONLY_ENTRYPOINT_ID",
    "AWS_READ_ONLY_SLICE_ID",
    "AdminShellRequest",
    "AdminShellSelection",
    "AdminSurfaceCatalogEntry",
    "AdminTenantScope",
    "AdminToolRegistryEntry",
    "build_admin_surface_catalog",
    "build_admin_tool_registry_entries",
    "resolve_admin_shell_request",
]
