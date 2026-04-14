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

TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA = "mycite.v2.portal.operational_status.request.v1"
TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA = "mycite.v2.portal.audit_activity.request.v1"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA = "mycite.v2.portal.profile_basics_write.request.v1"

TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID = "portal.home.tenant_status"
TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID = "portal.operational_status"
TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID = "portal.audit_activity"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID = "portal.profile_basics_write"

BAND1_TRUSTED_TENANT_READ_ONLY_NAME = "Band 1 Trusted-Tenant Read-Only"
BAND2_TRUSTED_TENANT_WRITABLE_NAME = "Band 2 Trusted-Tenant Writable Slice"
TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS = "trusted-tenant-read-only"
TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS = "trusted-tenant-writable"

BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID = "band1.portal_home_tenant_status"
BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID = "band1.operational_status_surface"
BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID = "band1.audit_activity_visibility"
BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID = "band2.profile_basics_write_surface"

TRUSTED_TENANT_CANONICAL_LANDING_PAGE_ROUTE = "/portal"
TRUSTED_TENANT_HOME_PAGE_ALIAS_ROUTE = "/portal/home"
TRUSTED_TENANT_HOME_API_ROUTE = "/portal/api/v2/tenant/home"
TRUSTED_TENANT_OPERATIONAL_STATUS_PAGE_ROUTE = "/portal/status"
TRUSTED_TENANT_OPERATIONAL_STATUS_API_ROUTE = "/portal/api/v2/tenant/operational-status"
TRUSTED_TENANT_AUDIT_ACTIVITY_PAGE_ROUTE = "/portal/activity"
TRUSTED_TENANT_AUDIT_ACTIVITY_API_ROUTE = "/portal/api/v2/tenant/audit-activity"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_PAGE_ROUTE = "/portal/profile-basics"
TRUSTED_TENANT_PROFILE_BASICS_WRITE_API_ROUTE = "/portal/api/v2/tenant/profile-basics"

TRUSTED_TENANT_SURFACE_POSTURE_PENDING_AUDIT = "pending_audit"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


def _dedupe_entries(entries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries or []:
        label = _as_text(entry.get("label"))
        meta = _as_text(entry.get("meta"))
        key = (label, meta)
        if not label and not meta:
            continue
        if key in seen:
            continue
        normalized.append(dict(entry))
        seen.add(key)
    return normalized


def _static_control_panel_entry(
    *,
    label: str,
    meta: str,
    active: bool = False,
) -> dict[str, Any]:
    return {
        "label": _as_text(label),
        "meta": _as_text(meta),
        "active": bool(active),
    }


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
    entrypoint_id: str
    page_route: str
    api_route: str
    request_schema: str
    label: str
    icon_id: str
    nav_group: str
    nav_kind: str
    active_service: str
    control_panel_kind: str
    exposure_status: str
    read_write_posture: str
    status_summary: str
    surface_kind: str
    surface_posture: str = TRUSTED_TENANT_SURFACE_POSTURE_PENDING_AUDIT
    audience: str = "trusted-tenant"
    launchable: bool = True
    default_surface: bool = False

    def __post_init__(self) -> None:
        if not _as_text(self.slice_id):
            raise ValueError("trusted_tenant_portal_surface.slice_id is required")
        if not _as_text(self.entrypoint_id):
            raise ValueError("trusted_tenant_portal_surface.entrypoint_id is required")
        if not _as_text(self.page_route):
            raise ValueError("trusted_tenant_portal_surface.page_route is required")
        if not _as_text(self.api_route):
            raise ValueError("trusted_tenant_portal_surface.api_route is required")
        if not _as_text(self.request_schema):
            raise ValueError("trusted_tenant_portal_surface.request_schema is required")
        if not _as_text(self.label):
            raise ValueError("trusted_tenant_portal_surface.label is required")
        if not _as_text(self.icon_id):
            raise ValueError("trusted_tenant_portal_surface.icon_id is required")
        if not _as_text(self.nav_group):
            raise ValueError("trusted_tenant_portal_surface.nav_group is required")
        if not _as_text(self.nav_kind):
            raise ValueError("trusted_tenant_portal_surface.nav_kind is required")
        if not _as_text(self.active_service):
            raise ValueError("trusted_tenant_portal_surface.active_service is required")
        if not _as_text(self.control_panel_kind):
            raise ValueError("trusted_tenant_portal_surface.control_panel_kind is required")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("trusted_tenant_portal_surface.read_write_posture must be read-only or write")

    def to_dict(self) -> dict[str, Any]:
        return {
            "slice_id": self.slice_id,
            "entrypoint_id": self.entrypoint_id,
            "page_route": self.page_route,
            "api_route": self.api_route,
            "request_schema": self.request_schema,
            "label": self.label,
            "icon_id": self.icon_id,
            "nav_group": self.nav_group,
            "nav_kind": self.nav_kind,
            "active_service": self.active_service,
            "control_panel_kind": self.control_panel_kind,
            "exposure_status": self.exposure_status,
            "read_write_posture": self.read_write_posture,
            "status_summary": self.status_summary,
            "surface_kind": self.surface_kind,
            "surface_posture": self.surface_posture,
            "audience": self.audience,
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
            entrypoint_id=TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID,
            page_route=TRUSTED_TENANT_CANONICAL_LANDING_PAGE_ROUTE,
            api_route=TRUSTED_TENANT_HOME_API_ROUTE,
            request_schema=TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA,
            label="Portal Home and Tenant Status",
            icon_id="tenant_home",
            nav_group="tenant_surfaces",
            nav_kind="root",
            active_service="home",
            control_panel_kind="tenant_home_control_panel",
            exposure_status="implemented_trusted_tenant_read_only",
            read_write_posture="read-only",
            status_summary="default_landing",
            surface_kind="tenant_home_status",
            default_surface=True,
        ),
        TrustedTenantPortalSurfaceCatalogEntry(
            slice_id=BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID,
            entrypoint_id=TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID,
            page_route=TRUSTED_TENANT_OPERATIONAL_STATUS_PAGE_ROUTE,
            api_route=TRUSTED_TENANT_OPERATIONAL_STATUS_API_ROUTE,
            request_schema=TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA,
            label="Operational Status",
            icon_id="tenant_status",
            nav_group="tenant_surfaces",
            nav_kind="surface",
            active_service="status",
            control_panel_kind="tenant_operational_status_control_panel",
            exposure_status="implemented_trusted_tenant_read_only",
            read_write_posture="read-only",
            status_summary="read_only_status_surface",
            surface_kind="operational_status",
        ),
        TrustedTenantPortalSurfaceCatalogEntry(
            slice_id=BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID,
            entrypoint_id=TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID,
            page_route=TRUSTED_TENANT_AUDIT_ACTIVITY_PAGE_ROUTE,
            api_route=TRUSTED_TENANT_AUDIT_ACTIVITY_API_ROUTE,
            request_schema=TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA,
            label="Recent Activity",
            icon_id="tenant_activity",
            nav_group="tenant_surfaces",
            nav_kind="surface",
            active_service="activity",
            control_panel_kind="tenant_audit_activity_control_panel",
            exposure_status="implemented_trusted_tenant_read_only",
            read_write_posture="read-only",
            status_summary="recent_local_audit_window",
            surface_kind="audit_activity",
        ),
        TrustedTenantPortalSurfaceCatalogEntry(
            slice_id=BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID,
            entrypoint_id=TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID,
            page_route=TRUSTED_TENANT_PROFILE_BASICS_WRITE_PAGE_ROUTE,
            api_route=TRUSTED_TENANT_PROFILE_BASICS_WRITE_API_ROUTE,
            request_schema=TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA,
            label="Profile Basics",
            icon_id="tenant_profile",
            nav_group="tenant_surfaces",
            nav_kind="surface",
            active_service="profile",
            control_panel_kind="tenant_profile_basics_control_panel",
            exposure_status="implemented_trusted_tenant_writable",
            read_write_posture="write",
            status_summary="bounded_profile_basics_write",
            surface_kind="profile_basics_write",
        ),
    )


def resolve_trusted_tenant_portal_surface(
    slice_id: object,
) -> TrustedTenantPortalSurfaceCatalogEntry | None:
    normalized_slice_id = _as_text(slice_id)
    for entry in build_trusted_tenant_portal_surface_catalog():
        if entry.slice_id == normalized_slice_id:
            return entry
    return None


def build_trusted_tenant_portal_route_catalog() -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "page_route": entry.page_route,
            "api_route": entry.api_route,
            "request_schema": entry.request_schema,
            "slice_id": entry.slice_id,
            "workbench_kind": entry.surface_kind,
        }
        for entry in build_trusted_tenant_portal_surface_catalog()
    )


def _dispatch_body_for_surface(
    entry: TrustedTenantPortalSurfaceCatalogEntry,
    *,
    portal_tenant_id: str,
) -> dict[str, Any]:
    tenant_scope = {
        "scope_id": _as_text(portal_tenant_id) or "fnd",
        "audience": entry.audience,
    }
    if entry.request_schema == TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA:
        return {
            "schema": entry.request_schema,
            "requested_slice_id": entry.slice_id,
            "tenant_scope": tenant_scope,
        }
    return {
        "schema": entry.request_schema,
        "tenant_scope": tenant_scope,
    }


def build_trusted_tenant_portal_dispatch_bodies(
    *,
    portal_tenant_id: str,
) -> dict[str, dict[str, Any]]:
    return {
        entry.slice_id: _dispatch_body_for_surface(entry, portal_tenant_id=portal_tenant_id)
        for entry in build_trusted_tenant_portal_surface_catalog()
    }


def build_trusted_tenant_activity_items(
    *,
    portal_tenant_id: str,
    active_surface_id: str,
) -> list[dict[str, Any]]:
    bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    items: list[dict[str, Any]] = []
    for entry in build_trusted_tenant_portal_surface_catalog():
        if not entry.launchable:
            continue
        items.append(
            {
                "slice_id": entry.slice_id,
                "label": entry.label,
                "active": entry.slice_id == _as_text(active_surface_id),
                "href": entry.page_route,
                "aria_label": entry.label,
                "icon_id": entry.icon_id,
                "nav_group": entry.nav_group,
                "nav_kind": entry.nav_kind,
                "nav_behavior": "canonical",
                "dispatch_route": entry.api_route,
                "request_schema": entry.request_schema,
                "entrypoint_id": entry.entrypoint_id,
                "shell_request": bodies.get(entry.slice_id),
            }
        )
    return items


def build_trusted_tenant_control_panel_navigation_entries(
    *,
    portal_tenant_id: str,
    active_surface_id: str,
) -> list[dict[str, Any]]:
    bodies = build_trusted_tenant_portal_dispatch_bodies(portal_tenant_id=portal_tenant_id)
    entries: list[dict[str, Any]] = []
    for entry in build_trusted_tenant_portal_surface_catalog():
        if not entry.launchable:
            continue
        entries.append(
            {
                "label": entry.label,
                "meta": entry.status_summary,
                "active": entry.slice_id == _as_text(active_surface_id),
                "href": entry.page_route,
                "nav_behavior": "canonical",
                "dispatch_route": entry.api_route,
                "request_schema": entry.request_schema,
                "entrypoint_id": entry.entrypoint_id,
                "shell_request": bodies.get(entry.slice_id),
            }
        )
    return entries


def build_trusted_tenant_control_panel_region(
    *,
    portal_tenant_id: str,
    active_surface_id: str,
    title: str,
    subtitle: str,
    current_rollout_band: str,
    exposure_status: str,
    read_write_posture: str,
    attention_entries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    context_entries: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> dict[str, Any]:
    active_surface = resolve_trusted_tenant_portal_surface(active_surface_id)
    region: dict[str, Any] = {
        "schema": TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": (
            active_surface.control_panel_kind
            if active_surface is not None
            else "tenant_control_panel"
        ),
        "title": _as_text(title),
        "subtitle": _as_text(subtitle),
        "sections": [],
    }
    normalized_attention = _dedupe_entries(list(attention_entries or []))
    if normalized_attention:
        region["sections"].append(
            {
                "title": "Attention",
                "entries": normalized_attention,
            }
        )
    baseline_context = [
        _static_control_panel_entry(
            label="Current surface",
            meta=active_surface.label if active_surface is not None else _as_text(active_surface_id),
        ),
        _static_control_panel_entry(label="Rollout band", meta=current_rollout_band),
        _static_control_panel_entry(label="Exposure posture", meta=exposure_status),
        _static_control_panel_entry(label="Read/write posture", meta=read_write_posture),
        _static_control_panel_entry(label="Tenant scope", meta=portal_tenant_id),
    ]
    normalized_context = baseline_context + _dedupe_entries(list(context_entries or []))
    region["sections"].append(
        {
            "title": "Context",
            "entries": normalized_context,
        }
    )
    region["sections"].append(
        {
            "title": "Approved tenant surfaces",
            "entries": build_trusted_tenant_control_panel_navigation_entries(
                portal_tenant_id=portal_tenant_id,
                active_surface_id=active_surface_id,
            ),
        }
    )
    return region


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

    available_surface_ids = {
        entry.slice_id
        for entry in build_trusted_tenant_portal_surface_catalog()
        if entry.request_schema == TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA
    }
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
    active_surface = resolve_trusted_tenant_portal_surface(active_surface_id)
    return {
        "schema": TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA,
        "composition_mode": "system",
        "active_service": active_surface.active_service if active_surface is not None else "home",
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
    "BAND1_AUDIT_ACTIVITY_VISIBILITY_SLICE_ID",
    "BAND1_OPERATIONAL_STATUS_SURFACE_SLICE_ID",
    "BAND1_PORTAL_HOME_TENANT_STATUS_SLICE_ID",
    "BAND1_TRUSTED_TENANT_READ_ONLY_NAME",
    "BAND2_PROFILE_BASICS_WRITE_SURFACE_SLICE_ID",
    "BAND2_TRUSTED_TENANT_WRITABLE_NAME",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_API_ROUTE",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_PAGE_ROUTE",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_REQUEST_SCHEMA",
    "TRUSTED_TENANT_AUDIT_ACTIVITY_ENTRYPOINT_ID",
    "TRUSTED_TENANT_CANONICAL_LANDING_PAGE_ROUTE",
    "TRUSTED_TENANT_HOME_API_ROUTE",
    "TRUSTED_TENANT_HOME_PAGE_ALIAS_ROUTE",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_API_ROUTE",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_PAGE_ROUTE",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_REQUEST_SCHEMA",
    "TRUSTED_TENANT_OPERATIONAL_STATUS_ENTRYPOINT_ID",
    "TRUSTED_TENANT_PORTAL_COMPOSITION_SCHEMA",
    "TRUSTED_TENANT_PORTAL_ENTRYPOINT_ID",
    "TRUSTED_TENANT_PORTAL_EXPOSURE_STATUS",
    "TRUSTED_TENANT_PORTAL_REGION_ACTIVITY_BAR_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REGION_CONTROL_PANEL_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REGION_INSPECTOR_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REGION_WORKBENCH_SCHEMA",
    "TRUSTED_TENANT_PORTAL_REQUEST_SCHEMA",
    "TRUSTED_TENANT_PORTAL_STATE_SCHEMA",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_API_ROUTE",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_ENTRYPOINT_ID",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_PAGE_ROUTE",
    "TRUSTED_TENANT_PROFILE_BASICS_WRITE_REQUEST_SCHEMA",
    "TRUSTED_TENANT_SURFACE_POSTURE_PENDING_AUDIT",
    "TRUSTED_TENANT_WRITABLE_EXPOSURE_STATUS",
    "TrustedTenantPortalChrome",
    "TrustedTenantPortalRequest",
    "TrustedTenantPortalScope",
    "TrustedTenantPortalSelection",
    "TrustedTenantPortalSurfaceCatalogEntry",
    "build_trusted_tenant_activity_items",
    "build_trusted_tenant_control_panel_navigation_entries",
    "build_trusted_tenant_control_panel_region",
    "build_trusted_tenant_portal_composition_payload",
    "build_trusted_tenant_portal_dispatch_bodies",
    "build_trusted_tenant_portal_route_catalog",
    "build_trusted_tenant_portal_surface_catalog",
    "resolve_trusted_tenant_portal_request",
    "resolve_trusted_tenant_portal_surface",
]
