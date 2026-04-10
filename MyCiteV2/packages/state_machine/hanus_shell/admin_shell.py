from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ADMIN_SHELL_REQUEST_SCHEMA = "mycite.v2.admin.shell.request.v1"
ADMIN_SHELL_STATE_SCHEMA = "mycite.v2.admin.shell.state.v1"

ADMIN_BAND0_NAME = "Admin Band 0 Internal Admin Replacement"
ADMIN_BAND1_AWS_NAME = "Admin Band 1 Trusted-Tenant AWS Read-Only"
ADMIN_BAND2_AWS_NAME = "Admin Band 2 Trusted-Tenant AWS Narrow Write"

ADMIN_EXPOSURE_INTERNAL_ONLY = "internal-only"
ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY = "trusted-tenant-read-only"
ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE = "trusted-tenant-narrow-write"
ADMIN_ENTRYPOINT_ID = "admin.shell_entry"

ADMIN_SHELL_ENTRY_SLICE_ID = "admin_band0.shell_entry"
ADMIN_HOME_STATUS_SLICE_ID = "admin_band0.home_status"
ADMIN_TOOL_REGISTRY_SLICE_ID = "admin_band0.tool_registry"
AWS_READ_ONLY_SLICE_ID = "admin_band1.aws_read_only_surface"
AWS_NARROW_WRITE_SLICE_ID = "admin_band2.aws_narrow_write_surface"
AWS_READ_ONLY_ENTRYPOINT_ID = "admin.aws.read_only"
AWS_NARROW_WRITE_ENTRYPOINT_ID = "admin.aws.narrow_write"

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
class AdminToolLaunchDecision:
    slice_id: str
    entrypoint_id: str
    allowed: bool
    selection_status: str
    reason_code: str = ""
    reason_message: str = ""
    exposure_status: str = ""

    def __post_init__(self) -> None:
        slice_id = _as_text(self.slice_id)
        entrypoint_id = _as_text(self.entrypoint_id)
        selection_status = _as_text(self.selection_status).lower()
        if not slice_id:
            raise ValueError("admin_tool_launch_decision.slice_id is required")
        if not entrypoint_id:
            raise ValueError("admin_tool_launch_decision.entrypoint_id is required")
        if selection_status not in {"available", "gated", "audience_denied", "unknown"}:
            raise ValueError("admin_tool_launch_decision.selection_status is invalid")
        object.__setattr__(self, "slice_id", slice_id)
        object.__setattr__(self, "entrypoint_id", entrypoint_id)
        object.__setattr__(self, "selection_status", selection_status)
        object.__setattr__(self, "reason_code", _as_text(self.reason_code).lower())
        object.__setattr__(self, "reason_message", _as_text(self.reason_message))
        object.__setattr__(self, "exposure_status", _as_text(self.exposure_status))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ADMIN_SHELL_STATE_SCHEMA,
            "slice_id": self.slice_id,
            "entrypoint_id": self.entrypoint_id,
            "allowed": bool(self.allowed),
            "selection_status": self.selection_status,
            "reason_code": self.reason_code,
            "reason_message": self.reason_message,
            "exposure_status": self.exposure_status,
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
            exposure_status="implemented_trusted_tenant_read_only",
            read_write_posture="read-only",
            status_summary="launchable_read_only",
            audience="trusted-tenant-admin",
            internal_only_reason="",
            launchable=True,
        ),
        AdminToolRegistryEntry(
            tool_id="aws_narrow_write",
            label="AWS Admin Narrow Write",
            slice_id=AWS_NARROW_WRITE_SLICE_ID,
            entrypoint_id=AWS_NARROW_WRITE_ENTRYPOINT_ID,
            admin_band=ADMIN_BAND2_AWS_NAME,
            exposure_status="implemented_trusted_tenant_narrow_write",
            read_write_posture="write",
            status_summary="launchable_narrow_write",
            audience="trusted-tenant-admin",
            internal_only_reason="",
            launchable=True,
        ),
    )


def resolve_admin_tool_launch(
    *,
    slice_id: object,
    audience: object,
    expected_entrypoint_id: object,
) -> AdminToolLaunchDecision:
    requested_slice_id = _as_text(slice_id)
    normalized_audience = _as_text(audience).lower() or "internal"
    normalized_entrypoint_id = _as_text(expected_entrypoint_id)

    for entry in build_admin_tool_registry_entries():
        if entry.slice_id != requested_slice_id:
            continue
        if entry.entrypoint_id != normalized_entrypoint_id:
            return AdminToolLaunchDecision(
                slice_id=entry.slice_id,
                entrypoint_id=entry.entrypoint_id,
                allowed=False,
                selection_status="unknown",
                reason_code="catalog_mismatch",
                reason_message="Requested AWS entrypoint does not match the shell-owned registry.",
                exposure_status=entry.exposure_status,
            )
        if not entry.launchable:
            return AdminToolLaunchDecision(
                slice_id=entry.slice_id,
                entrypoint_id=entry.entrypoint_id,
                allowed=False,
                selection_status="gated",
                reason_code="slice_gated",
                reason_message=entry.internal_only_reason or "Requested admin tool slice is not launchable.",
                exposure_status=entry.exposure_status,
            )
        if normalized_audience == "trusted-tenant" and entry.audience != "trusted-tenant-admin":
            return AdminToolLaunchDecision(
                slice_id=entry.slice_id,
                entrypoint_id=entry.entrypoint_id,
                allowed=False,
                selection_status="audience_denied",
                reason_code="audience_not_allowed",
                reason_message="Requested admin tool slice is not approved for the requested audience.",
                exposure_status=entry.exposure_status,
            )
        if normalized_audience not in _ALLOWED_AUDIENCES:
            return AdminToolLaunchDecision(
                slice_id=entry.slice_id,
                entrypoint_id=entry.entrypoint_id,
                allowed=False,
                selection_status="audience_denied",
                reason_code="audience_not_allowed",
                reason_message="Requested admin tool slice is not approved for the requested audience.",
                exposure_status=entry.exposure_status,
            )
        return AdminToolLaunchDecision(
            slice_id=entry.slice_id,
            entrypoint_id=entry.entrypoint_id,
            allowed=True,
            selection_status="available",
            exposure_status=entry.exposure_status,
        )

    return AdminToolLaunchDecision(
        slice_id=requested_slice_id or AWS_READ_ONLY_SLICE_ID,
        entrypoint_id=normalized_entrypoint_id or AWS_READ_ONLY_ENTRYPOINT_ID,
        allowed=False,
        selection_status="unknown",
        reason_code="slice_unknown",
        reason_message="Requested admin tool slice is not registered in the shell-owned registry.",
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
                active_surface_id=ADMIN_TOOL_REGISTRY_SLICE_ID,
                selection_status="gated",
                allowed=False,
                reason_code="launch_via_registry",
                reason_message="AWS tool slices launch through the shell-owned registry and their cataloged runtime entrypoints.",
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
    "ADMIN_EXPOSURE_TRUSTED_TENANT_NARROW_WRITE",
    "ADMIN_EXPOSURE_TRUSTED_TENANT_READ_ONLY",
    "ADMIN_HOME_STATUS_SLICE_ID",
    "ADMIN_SHELL_ENTRY_SLICE_ID",
    "ADMIN_SHELL_REQUEST_SCHEMA",
    "ADMIN_SHELL_STATE_SCHEMA",
    "ADMIN_TOOL_REGISTRY_SLICE_ID",
    "AWS_NARROW_WRITE_SLICE_ID",
    "AWS_NARROW_WRITE_ENTRYPOINT_ID",
    "AWS_READ_ONLY_ENTRYPOINT_ID",
    "AWS_READ_ONLY_SLICE_ID",
    "AdminShellRequest",
    "AdminShellSelection",
    "AdminSurfaceCatalogEntry",
    "AdminTenantScope",
    "AdminToolLaunchDecision",
    "AdminToolRegistryEntry",
    "build_admin_surface_catalog",
    "build_admin_tool_registry_entries",
    "resolve_admin_tool_launch",
    "resolve_admin_shell_request",
]
