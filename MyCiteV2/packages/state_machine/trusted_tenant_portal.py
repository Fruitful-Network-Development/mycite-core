from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA = "mycite.v2.portal.tenant_home.request.v1"
TRUSTED_TENANT_PORTAL_STATE_SCHEMA = "mycite.v2.portal.tenant_home.state.v1"
TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA = "mycite.v2.portal.tenant_home.composition.v1"
TRUSTED_TENANT_PORTAL_REGION_ACTIVITY_BAR_SCHEMA = "mycite.v2.portal.tenant_home.region.activity_bar.v1"
TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA = "mycite.v2.portal.tenant_home.region.control_panel.v1"
TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA = "mycite.v2.portal.tenant_home.region.workbench.v1"
TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA = "mycite.v2.portal.tenant_home.region.inspector.v1"

BAND1_TRUSTED_TENANT_READ_ONLY_NAME = "Band 1 Trusted-Tenant Read-Only"
TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS = "trusted-tenant-read-only"
BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID = "band1.portal_home_tenant_status"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


@dataclass(frozen=True)
class TrustedTenantPortalScope:
    scope_id: str
    audience: str = "trusted-tenant"

    def __post_init__(self) -> None:
        scope_id = _as_text(self.scope_id)
        audience = _as_text(self.audience).lower() or "trusted-tenant"
        if not scope_id:
            raise ValueError("trusted_tenant_portal_scope.scope_id is required")
        object.__setattr__(self, "scope_id", scope_id)
        object.__setattr__(self, "audience", audience)

    def to_dict(self) -> dict[str, str]:
        return {"scope_id": self.scope_id, "audience": self.audience}

    @classmethod
    def from_value(cls, payload: dict[str, Any] | str | None) -> "TrustedTenantPortalScope":
        if payload is None:
            return cls(scope_id="fnd")
        if isinstance(payload, str):
            return cls(scope_id=payload)
        if isinstance(payload, dict):
            return cls(scope_id=payload.get("scope_id") or payload.get("tenant_id"), audience=payload.get("audience"))
        raise ValueError("trusted_tenant_portal_scope must be a dict, string, or None")


@dataclass(frozen=True)
class TrustedTenantPortalChrome:
    inspector_collapsed: bool | None = None
    control_panel_collapsed: bool | None = None

    def __post_init__(self) -> None:
        if self.inspector_collapsed is not None and not isinstance(self.inspector_collapsed, bool):
            raise ValueError("trusted_tenant_portal_chrome.inspector_collapsed must be a bool or null")
        if self.control_panel_collapsed is not None and not isinstance(self.control_panel_collapsed, bool):
            raise ValueError("trusted_tenant_portal_chrome.control_panel_collapsed must be a bool or null")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.inspector_collapsed is not None:
            out["inspector_collapsed"] = self.inspector_collapsed
        if self.control_panel_collapsed is not None:
            out["control_panel_collapsed"] = self.control_panel_collapsed
        return out

    @classmethod
    def from_value(cls, payload: dict[str, Any] | None) -> "TrustedTenantPortalChrome":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("trusted_tenant_portal_chrome must be a dict or null")
        return cls(
            inspector_collapsed=payload.get("inspector_collapsed"),
            control_panel_collapsed=payload.get("control_panel_collapsed"),
        )


@dataclass(frozen=True)
class TrustedTenantPortalRequest:
    requested_slice_id: str = BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID
    tenant_scope: TrustedTenantPortalScope = field(
        default_factory=lambda: TrustedTenantPortalScope(scope_id="fnd")
    )
    shell_chrome: TrustedTenantPortalChrome = field(default_factory=TrustedTenantPortalChrome)
    schema: str = field(default=TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        requested_slice_id = _as_text(self.requested_slice_id) or BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID
        tenant_scope = (
            self.tenant_scope
            if isinstance(self.tenant_scope, TrustedTenantPortalScope)
            else TrustedTenantPortalScope.from_value(self.tenant_scope)
        )
        shell_chrome = (
            self.shell_chrome
            if isinstance(self.shell_chrome, TrustedTenantPortalChrome)
            else TrustedTenantPortalChrome.from_value(self.shell_chrome)
        )
        object.__setattr__(self, "requested_slice_id", requested_slice_id)
        object.__setattr__(self, "tenant_scope", tenant_scope)
        object.__setattr__(self, "shell_chrome", shell_chrome)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "requested_slice_id": self.requested_slice_id,
            "tenant_scope": self.tenant_scope.to_dict(),
        }
        chrome = self.shell_chrome.to_dict()
        if chrome:
            payload["shell_chrome"] = chrome
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "TrustedTenantPortalRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("trusted_tenant_portal_request must be a dict")
        _require_schema(
            payload,
            expected=TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
            field_name="trusted_tenant_portal_request.schema",
        )
        return cls(
            requested_slice_id=payload.get("requested_slice_id") or BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            tenant_scope=TrustedTenantPortalScope.from_value(payload.get("tenant_scope")),
            shell_chrome=TrustedTenantPortalChrome.from_value(
                payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
            ),
        )


@dataclass(frozen=True)
class TrustedTenantPortalSurfaceCatalogEntry:
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
            raise ValueError("trusted_tenant_portal_surface.slice_id is required")
        if not _as_text(self.label):
            raise ValueError("trusted_tenant_portal_surface.label is required")
        if self.read_write_posture != "read-only":
            raise ValueError("trusted_tenant_portal_surface.read_write_posture must be read-only")

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
class TrustedTenantPortalSelection:
    requested_slice_id: str
    active_surface_id: str
    selection_status: str
    allowed: bool
    reason_code: str = ""
    reason_message: str = ""
    schema: str = field(default=TRUSTED_TENANT_PORTAL_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        requested_slice_id = _as_text(self.requested_slice_id) or BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID
        active_surface_id = _as_text(self.active_surface_id) or BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID
        selection_status = _as_text(self.selection_status).lower()
        if selection_status not in {"available", "audience_denied", "unknown"}:
            raise ValueError("trusted_tenant_portal_selection.selection_status is invalid")
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


def build_trusted_tenant_portal_surface_catalog() -> tuple[TrustedTenantPortalSurfaceCatalogEntry, ...]:
    return (
        TrustedTenantPortalSurfaceCatalogEntry(
            slice_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            label="Portal Home and Tenant Status",
            exposure_status="implemented_trusted_tenant_read_only",
            read_write_posture="read-only",
            status_summary="default_landing",
            surface_kind="tenant_home_status",
            launchable=True,
            default_surface=True,
        ),
    )


def resolve_trusted_tenant_portal_request(
    request: TrustedTenantPortalRequest | dict[str, Any] | None,
) -> TrustedTenantPortalSelection:
    normalized_request = (
        request
        if isinstance(request, TrustedTenantPortalRequest)
        else TrustedTenantPortalRequest.from_dict(request)
    )
    requested_slice_id = normalized_request.requested_slice_id
    audience = normalized_request.tenant_scope.audience

    if audience != "trusted-tenant":
        return TrustedTenantPortalSelection(
            requested_slice_id=requested_slice_id,
            active_surface_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            selection_status="audience_denied",
            allowed=False,
            reason_code="audience_not_allowed",
            reason_message="Trusted-tenant portal requests require trusted-tenant audience.",
        )

    available_surface_ids = {entry.slice_id for entry in build_trusted_tenant_portal_surface_catalog()}
    if requested_slice_id in available_surface_ids:
        return TrustedTenantPortalSelection(
            requested_slice_id=requested_slice_id,
            active_surface_id=requested_slice_id,
            selection_status="available",
            allowed=True,
        )

    return TrustedTenantPortalSelection(
        requested_slice_id=requested_slice_id,
        active_surface_id=BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        selection_status="unknown",
        allowed=False,
        reason_code="slice_unknown",
        reason_message="Trusted-tenant portal slice is not approved for this landing surface.",
    )


def build_trusted_tenant_portal_dispatch_bodies(
    *,
    portal_tenant_id: str,
) -> dict[str, dict[str, Any]]:
    tenant = _as_text(portal_tenant_id) or "fnd"
    return {
        BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID: {
            "schema": TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
            "requested_slice_id": BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
            "tenant_scope": {"scope_id": tenant, "audience": "trusted-tenant"},
        }
    }


def build_trusted_tenant_portal_composition_payload(
    *,
    active_surface_id: str,
    portal_tenant_id: str,
    page_title: str,
    page_subtitle: str,
    activity_items: list[dict[str, Any]],
    control_panel: dict[str, Any],
    workbench: dict[str, Any],
    inspector: dict[str, Any],
    control_panel_collapsed: bool = False,
    inspector_collapsed: bool = True,
) -> dict[str, Any]:
    return {
        "schema": TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA,
        "composition_mode": "system",
        "active_service": "home",
        "active_surface_id": _as_text(active_surface_id) or BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID,
        "active_tool_slice_id": None,
        "foreground_shell_region": "center-workbench",
        "control_panel_collapsed": bool(control_panel_collapsed),
        "inspector_collapsed": bool(inspector_collapsed),
        "portal_tenant_id": _as_text(portal_tenant_id) or "fnd",
        "page_title": _as_text(page_title) or "MyCite",
        "page_subtitle": _as_text(page_subtitle),
        "regions": {
            "activity_bar": {
                "schema": TRUSTED_TENANT_PORTAL_REGION_ACTIVITY_BAR_SCHEMA,
                "dispatch": "post_trusted_tenant_portal",
                "items": list(activity_items),
            },
            "control_panel": dict(control_panel),
            "workbench": dict(workbench),
            "inspector": dict(inspector),
        },
    }


__all__ = [
    "BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID",
    "BAND1_TRUSTED_TENANT_READ_ONLY_NAME",
    "TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA",
    "TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS",
    "TRUSTED_TENANT_PORTAL_REGION_ACTIVITY_BAR_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA",
    "TRUSTED_TENANT_PORTAL_STATE_SCHEMA",
    "TrustedTenantPortalChrome",
    "TrustedTenantPortalRequest",
    "TrustedTenantPortalScope",
    "TrustedTenantPortalSelection",
    "TrustedTenantPortalSurfaceCatalogEntry",
    "build_trusted_tenant_portal_composition_payload",
    "build_trusted_tenant_portal_dispatch_bodies",
    "build_trusted_tenant_portal_surface_catalog",
    "resolve_trusted_tenant_portal_request",
]
