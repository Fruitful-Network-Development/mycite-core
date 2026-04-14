from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PORTAL_SHELL_REQUEST_SCHEMA = "mycite.v2.portal.shell.request.v1"
PORTAL_SHELL_STATE_SCHEMA = "mycite.v2.portal.shell.state.v1"
PORTAL_SHELL_COMPOSITION_SCHEMA = "mycite.v2.portal.shell.composition.v1"
PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA = "mycite.v2.portal.shell.region.activity_bar.v1"
PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA = "mycite.v2.portal.shell.region.control_panel.v1"
PORTAL_SHELL_REGION_WORKBENCH_SCHEMA = "mycite.v2.portal.shell.region.workbench.v1"
PORTAL_SHELL_REGION_INSPECTOR_SCHEMA = "mycite.v2.portal.shell.region.inspector.v1"
PORTAL_SURFACE_CATALOG_ENTRY_SCHEMA = "mycite.v2.portal.surface_catalog.entry.v1"
PORTAL_TOOL_REGISTRY_ENTRY_SCHEMA = "mycite.v2.portal.tool_registry.entry.v1"

SYSTEM_ROOT_SURFACE_ID = "system.root"
SYSTEM_OPERATIONAL_STATUS_SURFACE_ID = "system.operational_status"
SYSTEM_ACTIVITY_SURFACE_ID = "system.activity"
SYSTEM_PROFILE_BASICS_SURFACE_ID = "system.profile_basics"
NETWORK_ROOT_SURFACE_ID = "network.root"
UTILITIES_ROOT_SURFACE_ID = "utilities.root"
UTILITIES_TOOL_EXPOSURE_SURFACE_ID = "utilities.tool_exposure"
UTILITIES_INTEGRATIONS_SURFACE_ID = "utilities.integrations"

AWS_TOOL_SURFACE_ID = "system.tools.aws"
AWS_NARROW_WRITE_TOOL_SURFACE_ID = "system.tools.aws_narrow_write"
AWS_CSM_SANDBOX_TOOL_SURFACE_ID = "system.tools.aws_csm_sandbox"
AWS_CSM_ONBOARDING_TOOL_SURFACE_ID = "system.tools.aws_csm_onboarding"
CTS_GIS_TOOL_SURFACE_ID = "system.tools.cts_gis"
FND_EBI_TOOL_SURFACE_ID = "system.tools.fnd_ebi"

PORTAL_SHELL_ENTRYPOINT_ID = "portal.shell"
AWS_TOOL_ENTRYPOINT_ID = "portal.system.tools.aws"
AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID = "portal.system.tools.aws_narrow_write"
AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID = "portal.system.tools.aws_csm_sandbox"
AWS_CSM_ONBOARDING_TOOL_ENTRYPOINT_ID = "portal.system.tools.aws_csm_onboarding"
CTS_GIS_TOOL_ENTRYPOINT_ID = "portal.system.tools.cts_gis"
FND_EBI_TOOL_ENTRYPOINT_ID = "portal.system.tools.fnd_ebi"

SYSTEM_ROOT_ROUTE = "/portal/system"
SYSTEM_OPERATIONAL_STATUS_ROUTE = "/portal/system/operational-status"
SYSTEM_ACTIVITY_ROUTE = "/portal/system/activity"
SYSTEM_PROFILE_BASICS_ROUTE = "/portal/system/profile-basics"
NETWORK_ROOT_ROUTE = "/portal/network"
UTILITIES_ROOT_ROUTE = "/portal/utilities"
UTILITIES_TOOL_EXPOSURE_ROUTE = "/portal/utilities/tool-exposure"
UTILITIES_INTEGRATIONS_ROUTE = "/portal/utilities/integrations"

AWS_TOOL_ROUTE = "/portal/system/tools/aws"
AWS_NARROW_WRITE_TOOL_ROUTE = "/portal/system/tools/aws-narrow-write"
AWS_CSM_SANDBOX_TOOL_ROUTE = "/portal/system/tools/aws-csm-sandbox"
AWS_CSM_ONBOARDING_TOOL_ROUTE = "/portal/system/tools/aws-csm-onboarding"
CTS_GIS_TOOL_ROUTE = "/portal/system/tools/cts-gis"
FND_EBI_TOOL_ROUTE = "/portal/system/tools/fnd-ebi"

PORTAL_SCOPE_DEFAULT_ID = "fnd"
SURFACE_POSTURE_WORKBENCH_PRIMARY = "workbench_primary"
SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY = "interface_panel_primary"
TOOL_KIND_GENERAL = "general_tool"
TOOL_KIND_SERVICE = "service_tool"
TOOL_KIND_HOST_ALIAS = "host_alias_tool"
ROOT_SURFACE_IDS = frozenset(
    {
        SYSTEM_ROOT_SURFACE_ID,
        NETWORK_ROOT_SURFACE_ID,
        UTILITIES_ROOT_SURFACE_ID,
    }
)
SYSTEM_SURFACE_IDS = frozenset(
    {
        SYSTEM_ROOT_SURFACE_ID,
        SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
        SYSTEM_ACTIVITY_SURFACE_ID,
        SYSTEM_PROFILE_BASICS_SURFACE_ID,
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
    }
)
NETWORK_SURFACE_IDS = frozenset({NETWORK_ROOT_SURFACE_ID})
UTILITIES_SURFACE_IDS = frozenset(
    {
        UTILITIES_ROOT_SURFACE_ID,
        UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        UTILITIES_INTEGRATIONS_SURFACE_ID,
    }
)
TOOL_SURFACE_IDS = frozenset(
    {
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
    }
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


def _normalize_capabilities(value: object, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str) and not _as_text(value):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list, tuple, or null")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        item = _as_text(raw_item).lower().replace("-", "_").replace(" ", "_")
        if not item or item in seen:
            continue
        normalized.append(item)
        seen.add(item)
    return tuple(normalized)


@dataclass(frozen=True)
class PortalScope:
    scope_id: str = PORTAL_SCOPE_DEFAULT_ID
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        scope_id = _as_text(self.scope_id) or PORTAL_SCOPE_DEFAULT_ID
        object.__setattr__(self, "scope_id", scope_id)
        object.__setattr__(
            self,
            "capabilities",
            _normalize_capabilities(self.capabilities, field_name="portal_scope.capabilities"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "capabilities": list(self.capabilities),
        }

    @classmethod
    def from_value(cls, payload: dict[str, Any] | str | None) -> "PortalScope":
        if payload is None:
            return cls()
        if isinstance(payload, str):
            return cls(scope_id=payload)
        if isinstance(payload, dict):
            return cls(
                scope_id=payload.get("scope_id") or payload.get("portal_instance_id") or PORTAL_SCOPE_DEFAULT_ID,
                capabilities=payload.get("capabilities"),
            )
        raise ValueError("portal_scope must be a dict, string, or null")


@dataclass(frozen=True)
class PortalShellChrome:
    inspector_collapsed: bool | None = None
    control_panel_collapsed: bool | None = None

    def __post_init__(self) -> None:
        if self.inspector_collapsed is not None and not isinstance(self.inspector_collapsed, bool):
            raise ValueError("shell_chrome.inspector_collapsed must be a bool or null")
        if self.control_panel_collapsed is not None and not isinstance(self.control_panel_collapsed, bool):
            raise ValueError("shell_chrome.control_panel_collapsed must be a bool or null")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.inspector_collapsed is not None:
            out["inspector_collapsed"] = self.inspector_collapsed
        if self.control_panel_collapsed is not None:
            out["control_panel_collapsed"] = self.control_panel_collapsed
        return out

    @classmethod
    def from_value(cls, payload: dict[str, Any] | None) -> "PortalShellChrome":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("shell_chrome must be a dict or null")
        return cls(
            inspector_collapsed=payload.get("inspector_collapsed"),
            control_panel_collapsed=payload.get("control_panel_collapsed"),
        )


@dataclass(frozen=True)
class PortalShellRequest:
    requested_surface_id: str = SYSTEM_ROOT_SURFACE_ID
    portal_scope: PortalScope = field(default_factory=PortalScope)
    shell_chrome: PortalShellChrome = field(default_factory=PortalShellChrome)
    schema: str = field(default=PORTAL_SHELL_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        requested_surface_id = _as_text(self.requested_surface_id) or SYSTEM_ROOT_SURFACE_ID
        portal_scope = self.portal_scope if isinstance(self.portal_scope, PortalScope) else PortalScope.from_value(self.portal_scope)
        shell_chrome = (
            self.shell_chrome
            if isinstance(self.shell_chrome, PortalShellChrome)
            else PortalShellChrome.from_value(self.shell_chrome)
        )
        object.__setattr__(self, "requested_surface_id", requested_surface_id)
        object.__setattr__(self, "portal_scope", portal_scope)
        object.__setattr__(self, "shell_chrome", shell_chrome)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "requested_surface_id": self.requested_surface_id,
            "portal_scope": self.portal_scope.to_dict(),
        }
        chrome = self.shell_chrome.to_dict()
        if chrome:
            payload["shell_chrome"] = chrome
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PortalShellRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("portal_shell_request must be a dict")
        _require_schema(payload, expected=PORTAL_SHELL_REQUEST_SCHEMA, field_name="portal_shell_request.schema")
        return cls(
            requested_surface_id=payload.get("requested_surface_id") or SYSTEM_ROOT_SURFACE_ID,
            portal_scope=PortalScope.from_value(payload.get("portal_scope")),
            shell_chrome=PortalShellChrome.from_value(
                payload.get("shell_chrome") if isinstance(payload.get("shell_chrome"), dict) else None
            ),
        )


@dataclass(frozen=True)
class PortalSurfaceCatalogEntry:
    surface_id: str
    label: str
    route: str
    root_surface_id: str
    surface_kind: str
    page_owner: str
    read_write_posture: str = "read-only"
    tool_id: str = ""
    launchable: bool = True
    default_surface: bool = False
    schema: str = field(default=PORTAL_SURFACE_CATALOG_ENTRY_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not _as_text(self.surface_id):
            raise ValueError("surface_catalog.surface_id is required")
        if not _as_text(self.label):
            raise ValueError("surface_catalog.label is required")
        if not _as_text(self.route):
            raise ValueError("surface_catalog.route is required")
        if self.root_surface_id not in ROOT_SURFACE_IDS:
            raise ValueError("surface_catalog.root_surface_id must be SYSTEM, NETWORK, or UTILITIES")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("surface_catalog.read_write_posture must be read-only or write")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "surface_id": self.surface_id,
            "label": self.label,
            "route": self.route,
            "root_surface_id": self.root_surface_id,
            "surface_kind": self.surface_kind,
            "page_owner": self.page_owner,
            "read_write_posture": self.read_write_posture,
            "tool_id": self.tool_id,
            "launchable": bool(self.launchable),
            "default_surface": bool(self.default_surface),
        }


@dataclass(frozen=True)
class PortalToolRegistryEntry:
    tool_id: str
    label: str
    surface_id: str
    entrypoint_id: str
    route: str
    tool_kind: str
    surface_posture: str
    read_write_posture: str
    required_capabilities: tuple[str, ...] = ()
    default_enabled: bool = True
    summary: str = ""
    schema: str = field(default=PORTAL_TOOL_REGISTRY_ENTRY_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not _as_text(self.tool_id):
            raise ValueError("tool_registry.tool_id is required")
        if self.surface_id not in TOOL_SURFACE_IDS:
            raise ValueError("tool_registry.surface_id must be a known tool surface")
        if self.tool_kind not in {TOOL_KIND_GENERAL, TOOL_KIND_SERVICE, TOOL_KIND_HOST_ALIAS}:
            raise ValueError("tool_registry.tool_kind is invalid")
        if self.surface_posture not in {SURFACE_POSTURE_WORKBENCH_PRIMARY, SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY}:
            raise ValueError("tool_registry.surface_posture is invalid")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("tool_registry.read_write_posture must be read-only or write")
        object.__setattr__(
            self,
            "required_capabilities",
            _normalize_capabilities(self.required_capabilities, field_name="tool_registry.required_capabilities"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "tool_id": self.tool_id,
            "label": self.label,
            "surface_id": self.surface_id,
            "entrypoint_id": self.entrypoint_id,
            "route": self.route,
            "tool_kind": self.tool_kind,
            "surface_posture": self.surface_posture,
            "read_write_posture": self.read_write_posture,
            "required_capabilities": list(self.required_capabilities),
            "default_enabled": bool(self.default_enabled),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PortalToolLaunchDecision:
    surface_id: str
    entrypoint_id: str
    allowed: bool
    selection_status: str
    reason_code: str = ""
    reason_message: str = ""

    def __post_init__(self) -> None:
        if self.selection_status not in {"available", "gated", "unknown"}:
            raise ValueError("tool_launch_decision.selection_status is invalid")


@dataclass(frozen=True)
class PortalShellSelection:
    requested_surface_id: str
    active_surface_id: str
    selection_status: str
    allowed: bool
    reason_code: str = ""
    reason_message: str = ""
    schema: str = field(default=PORTAL_SHELL_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if self.selection_status not in {"available", "gated", "unknown"}:
            raise ValueError("portal_shell_selection.selection_status is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "requested_surface_id": self.requested_surface_id,
            "active_surface_id": self.active_surface_id,
            "selection_status": self.selection_status,
            "allowed": bool(self.allowed),
            "reason_code": self.reason_code,
            "reason_message": self.reason_message,
        }


def build_portal_surface_catalog() -> tuple[PortalSurfaceCatalogEntry, ...]:
    return (
        PortalSurfaceCatalogEntry(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            label="System",
            route=SYSTEM_ROOT_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="system_root",
            page_owner="system",
            default_surface=True,
        ),
        PortalSurfaceCatalogEntry(
            surface_id=SYSTEM_OPERATIONAL_STATUS_SURFACE_ID,
            label="Operational Status",
            route=SYSTEM_OPERATIONAL_STATUS_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="system_operational_status",
            page_owner="system",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=SYSTEM_ACTIVITY_SURFACE_ID,
            label="Recent Activity",
            route=SYSTEM_ACTIVITY_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="system_activity",
            page_owner="system",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=SYSTEM_PROFILE_BASICS_SURFACE_ID,
            label="Profile Basics",
            route=SYSTEM_PROFILE_BASICS_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="system_profile_basics",
            page_owner="system",
            read_write_posture="write",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=NETWORK_ROOT_SURFACE_ID,
            label="Network",
            route=NETWORK_ROOT_ROUTE,
            root_surface_id=NETWORK_ROOT_SURFACE_ID,
            surface_kind="network_root",
            page_owner="network",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_ROOT_SURFACE_ID,
            label="Utilities",
            route=UTILITIES_ROOT_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_root",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
            label="Tool Exposure",
            route=UTILITIES_TOOL_EXPOSURE_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_tool_exposure",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=UTILITIES_INTEGRATIONS_SURFACE_ID,
            label="Integrations",
            route=UTILITIES_INTEGRATIONS_ROUTE,
            root_surface_id=UTILITIES_ROOT_SURFACE_ID,
            surface_kind="utilities_integrations",
            page_owner="utilities",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=AWS_TOOL_SURFACE_ID,
            label="AWS-CSM",
            route=AWS_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="aws",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID,
            label="AWS Narrow Write",
            route=AWS_NARROW_WRITE_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="aws_narrow_write",
            read_write_posture="write",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
            label="AWS Sandbox",
            route=AWS_CSM_SANDBOX_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="aws_csm_sandbox",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
            label="AWS Onboarding",
            route=AWS_CSM_ONBOARDING_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="aws_csm_onboarding",
            read_write_posture="write",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            label="CTS-GIS",
            route=CTS_GIS_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="cts_gis",
        ),
        PortalSurfaceCatalogEntry(
            surface_id=FND_EBI_TOOL_SURFACE_ID,
            label="FND-EBI",
            route=FND_EBI_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="fnd_ebi",
        ),
    )


def build_portal_tool_registry_entries() -> tuple[PortalToolRegistryEntry, ...]:
    return (
        PortalToolRegistryEntry(
            tool_id="aws",
            label="AWS-CSM",
            surface_id=AWS_TOOL_SURFACE_ID,
            entrypoint_id=AWS_TOOL_ENTRYPOINT_ID,
            route=AWS_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_WORKBENCH_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=(),
            summary="Operational visibility for AWS-CSM.",
        ),
        PortalToolRegistryEntry(
            tool_id="aws_narrow_write",
            label="AWS Narrow Write",
            surface_id=AWS_NARROW_WRITE_TOOL_SURFACE_ID,
            entrypoint_id=AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID,
            route=AWS_NARROW_WRITE_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_WORKBENCH_PRIMARY,
            read_write_posture="write",
            required_capabilities=(),
            summary="Bounded sender selection.",
        ),
        PortalToolRegistryEntry(
            tool_id="aws_csm_sandbox",
            label="AWS Sandbox",
            surface_id=AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
            entrypoint_id=AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID,
            route=AWS_CSM_SANDBOX_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_WORKBENCH_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("sandbox_projection",),
            default_enabled=False,
            summary="Sandbox projection surface.",
        ),
        PortalToolRegistryEntry(
            tool_id="aws_csm_onboarding",
            label="AWS Onboarding",
            surface_id=AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
            entrypoint_id=AWS_CSM_ONBOARDING_TOOL_ENTRYPOINT_ID,
            route=AWS_CSM_ONBOARDING_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_WORKBENCH_PRIMARY,
            read_write_posture="write",
            required_capabilities=("fnd_peripheral_routing",),
            summary="Mailbox onboarding workflow.",
        ),
        PortalToolRegistryEntry(
            tool_id="cts_gis",
            label="CTS-GIS",
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            entrypoint_id=CTS_GIS_TOOL_ENTRYPOINT_ID,
            route=CTS_GIS_TOOL_ROUTE,
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("datum_recognition", "spatial_projection"),
            summary="Spatial mediation and read-only diagnostics.",
        ),
        PortalToolRegistryEntry(
            tool_id="fnd_ebi",
            label="FND-EBI",
            surface_id=FND_EBI_TOOL_SURFACE_ID,
            entrypoint_id=FND_EBI_TOOL_ENTRYPOINT_ID,
            route=FND_EBI_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_WORKBENCH_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("hosted_site_visibility", "fnd_peripheral_routing"),
            summary="Hosted site operational visibility.",
        ),
    )


def resolve_portal_surface(surface_id: object) -> PortalSurfaceCatalogEntry | None:
    normalized_surface_id = _as_text(surface_id)
    for entry in build_portal_surface_catalog():
        if entry.surface_id == normalized_surface_id:
            return entry
    return None


def resolve_portal_tool_registry_entry(tool_id: object = "", *, surface_id: object = "") -> PortalToolRegistryEntry | None:
    normalized_tool_id = _as_text(tool_id)
    normalized_surface_id = _as_text(surface_id)
    for entry in build_portal_tool_registry_entries():
        if normalized_tool_id and entry.tool_id == normalized_tool_id:
            return entry
        if normalized_surface_id and entry.surface_id == normalized_surface_id:
            return entry
    return None


def canonical_route_for_surface(surface_id: object) -> str:
    entry = resolve_portal_surface(surface_id)
    return entry.route if entry is not None else SYSTEM_ROOT_ROUTE


def surface_root_id(surface_id: object) -> str:
    entry = resolve_portal_surface(surface_id)
    return entry.root_surface_id if entry is not None else SYSTEM_ROOT_SURFACE_ID


def is_tool_surface(surface_id: object) -> bool:
    return _as_text(surface_id) in TOOL_SURFACE_IDS


def requires_shell_state_machine(surface_id: object) -> bool:
    normalized_surface_id = _as_text(surface_id)
    return normalized_surface_id in SYSTEM_SURFACE_IDS


def resolve_portal_tool_launch(
    *,
    surface_id: object,
    expected_entrypoint_id: object,
) -> PortalToolLaunchDecision:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=surface_id)
    if tool_entry is None:
        return PortalToolLaunchDecision(
            surface_id=_as_text(surface_id),
            entrypoint_id=_as_text(expected_entrypoint_id),
            allowed=False,
            selection_status="unknown",
            reason_code="surface_unknown",
            reason_message="Requested tool surface is not registered.",
        )
    if tool_entry.entrypoint_id != _as_text(expected_entrypoint_id):
        return PortalToolLaunchDecision(
            surface_id=tool_entry.surface_id,
            entrypoint_id=tool_entry.entrypoint_id,
            allowed=False,
            selection_status="unknown",
            reason_code="catalog_mismatch",
            reason_message="Requested tool entrypoint does not match the surface catalog.",
        )
    return PortalToolLaunchDecision(
        surface_id=tool_entry.surface_id,
        entrypoint_id=tool_entry.entrypoint_id,
        allowed=True,
        selection_status="available",
    )


def resolve_portal_shell_request(request: PortalShellRequest | dict[str, Any] | None) -> PortalShellSelection:
    normalized_request = request if isinstance(request, PortalShellRequest) else PortalShellRequest.from_dict(request)
    requested_surface_id = normalized_request.requested_surface_id
    surface_entry = resolve_portal_surface(requested_surface_id)
    if surface_entry is None or not surface_entry.launchable:
        return PortalShellSelection(
            requested_surface_id=requested_surface_id,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            selection_status="unknown",
            allowed=False,
            reason_code="surface_unknown",
            reason_message=f"Surface is not approved: {requested_surface_id}",
        )
    if is_tool_surface(requested_surface_id):
        launch_decision = resolve_portal_tool_launch(
            surface_id=requested_surface_id,
            expected_entrypoint_id=resolve_portal_tool_registry_entry(surface_id=requested_surface_id).entrypoint_id,
        )
        if not launch_decision.allowed:
            return PortalShellSelection(
                requested_surface_id=requested_surface_id,
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                selection_status=launch_decision.selection_status,
                allowed=False,
                reason_code=launch_decision.reason_code,
                reason_message=launch_decision.reason_message,
            )
    return PortalShellSelection(
        requested_surface_id=requested_surface_id,
        active_surface_id=surface_entry.surface_id,
        selection_status="available",
        allowed=True,
    )


def build_portal_activity_dispatch_bodies(
    *,
    portal_instance_id: str,
) -> dict[str, dict[str, Any]]:
    scope = {"scope_id": _as_text(portal_instance_id) or PORTAL_SCOPE_DEFAULT_ID, "capabilities": []}
    return {
        entry.surface_id: {
            "schema": PORTAL_SHELL_REQUEST_SCHEMA,
            "requested_surface_id": entry.surface_id,
            "portal_scope": scope,
        }
        for entry in build_portal_surface_catalog()
    }


def activity_icon_id_for_surface(surface_id: object) -> str:
    normalized_surface_id = _as_text(surface_id)
    if normalized_surface_id == SYSTEM_ROOT_SURFACE_ID:
        return "system"
    if normalized_surface_id == NETWORK_ROOT_SURFACE_ID:
        return "network"
    if normalized_surface_id in {UTILITIES_ROOT_SURFACE_ID, UTILITIES_TOOL_EXPOSURE_SURFACE_ID, UTILITIES_INTEGRATIONS_SURFACE_ID}:
        return "utilities"
    if normalized_surface_id in {
        AWS_TOOL_SURFACE_ID,
        AWS_NARROW_WRITE_TOOL_SURFACE_ID,
        AWS_CSM_SANDBOX_TOOL_SURFACE_ID,
        AWS_CSM_ONBOARDING_TOOL_SURFACE_ID,
    }:
        return "aws"
    if normalized_surface_id == CTS_GIS_TOOL_SURFACE_ID:
        return "cts_gis"
    if normalized_surface_id == FND_EBI_TOOL_SURFACE_ID:
        return "fnd_ebi"
    if normalized_surface_id == SYSTEM_OPERATIONAL_STATUS_SURFACE_ID:
        return "system_status"
    if normalized_surface_id == SYSTEM_ACTIVITY_SURFACE_ID:
        return "system_activity"
    if normalized_surface_id == SYSTEM_PROFILE_BASICS_SURFACE_ID:
        return "system_profile"
    return "generic"


def map_surface_to_active_service(active_surface_id: str) -> str:
    root_id = surface_root_id(active_surface_id)
    if root_id == NETWORK_ROOT_SURFACE_ID:
        return "network"
    if root_id == UTILITIES_ROOT_SURFACE_ID:
        return "utilities"
    return "system"


def shell_composition_mode_for_surface(active_surface_id: str) -> str:
    if is_tool_surface(active_surface_id):
        return "tool"
    return "system"


def surface_posture_for_surface(active_surface_id: str) -> str:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=active_surface_id)
    return tool_entry.surface_posture if tool_entry is not None else SURFACE_POSTURE_WORKBENCH_PRIMARY


def foreground_region_for_surface(active_surface_id: str) -> str:
    if (
        shell_composition_mode_for_surface(active_surface_id) == "tool"
        and surface_posture_for_surface(active_surface_id) == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY
    ):
        return "interface-panel"
    return "center-workbench"


def inspector_collapsed_for_surface(active_surface_id: str) -> bool:
    if (
        shell_composition_mode_for_surface(active_surface_id) == "tool"
        and surface_posture_for_surface(active_surface_id) == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY
    ):
        return False
    return True


def apply_surface_posture_to_composition(composition: dict[str, Any]) -> None:
    if not isinstance(composition, dict):
        return
    active_surface_id = _as_text(composition.get("active_surface_id"))
    posture = surface_posture_for_surface(active_surface_id)
    regions = composition.get("regions")
    if not isinstance(regions, dict):
        return
    inspector = regions.get("inspector")
    if not isinstance(inspector, dict):
        return
    if posture != SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY:
        inspector.setdefault("primary_surface", False)
        inspector.setdefault("layout_mode", "sidebar")
        return
    if bool(composition.get("inspector_collapsed")):
        composition["foreground_shell_region"] = "center-workbench"
        inspector["primary_surface"] = False
        inspector["layout_mode"] = "dominant"
        regions["workbench"] = {
            "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
            "kind": "tool_collapsed_inspector",
            "title": _as_text((regions.get("workbench") or {}).get("title")) or "Tool surface",
            "subtitle": "Interface panel dismissed",
            "visible": True,
            "message": "This tool mediates primarily through the interface panel.",
            "action_label": "Reopen interface panel",
            "action_shell_chrome": {"inspector_collapsed": False},
        }
        return
    composition["foreground_shell_region"] = "interface-panel"
    inspector["primary_surface"] = True
    inspector["layout_mode"] = "dominant"


def build_shell_composition_payload(
    *,
    active_surface_id: str,
    portal_instance_id: str,
    page_title: str,
    page_subtitle: str,
    activity_items: list[dict[str, Any]],
    control_panel: dict[str, Any],
    workbench: dict[str, Any],
    inspector: dict[str, Any],
    control_panel_collapsed: bool = False,
) -> dict[str, Any]:
    mode = shell_composition_mode_for_surface(active_surface_id)
    active_tool_surface_id: str | None = None
    if mode == "tool":
        active_tool_surface_id = _as_text(active_surface_id)
    inspector_region = dict(inspector)
    inspector_region.setdefault(
        "primary_surface",
        bool(
            mode == "tool"
            and surface_posture_for_surface(active_surface_id) == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY
        ),
    )
    inspector_region.setdefault(
        "layout_mode",
        "dominant"
        if (
            mode == "tool"
            and surface_posture_for_surface(active_surface_id) == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY
        )
        else "sidebar",
    )
    return {
        "schema": PORTAL_SHELL_COMPOSITION_SCHEMA,
        "composition_mode": mode,
        "active_service": map_surface_to_active_service(active_surface_id),
        "active_surface_id": _as_text(active_surface_id),
        "active_tool_surface_id": active_tool_surface_id,
        "foreground_shell_region": foreground_region_for_surface(active_surface_id),
        "control_panel_collapsed": bool(control_panel_collapsed),
        "inspector_collapsed": inspector_collapsed_for_surface(active_surface_id),
        "portal_instance_id": _as_text(portal_instance_id) or PORTAL_SCOPE_DEFAULT_ID,
        "page_title": _as_text(page_title) or "MyCite",
        "page_subtitle": _as_text(page_subtitle),
        "regions": {
            "activity_bar": {
                "schema": PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA,
                "dispatch": "post_portal_shell",
                "items": list(activity_items),
            },
            "control_panel": dict(control_panel),
            "workbench": dict(workbench),
            "inspector": inspector_region,
        },
    }


__all__ = [
    "AWS_CSM_ONBOARDING_TOOL_ENTRYPOINT_ID",
    "AWS_CSM_ONBOARDING_TOOL_ROUTE",
    "AWS_CSM_ONBOARDING_TOOL_SURFACE_ID",
    "AWS_CSM_SANDBOX_TOOL_ENTRYPOINT_ID",
    "AWS_CSM_SANDBOX_TOOL_ROUTE",
    "AWS_CSM_SANDBOX_TOOL_SURFACE_ID",
    "AWS_NARROW_WRITE_TOOL_ENTRYPOINT_ID",
    "AWS_NARROW_WRITE_TOOL_ROUTE",
    "AWS_NARROW_WRITE_TOOL_SURFACE_ID",
    "AWS_TOOL_ENTRYPOINT_ID",
    "AWS_TOOL_ROUTE",
    "AWS_TOOL_SURFACE_ID",
    "CTS_GIS_TOOL_ENTRYPOINT_ID",
    "CTS_GIS_TOOL_ROUTE",
    "CTS_GIS_TOOL_SURFACE_ID",
    "FND_EBI_TOOL_ENTRYPOINT_ID",
    "FND_EBI_TOOL_ROUTE",
    "FND_EBI_TOOL_SURFACE_ID",
    "NETWORK_ROOT_ROUTE",
    "NETWORK_ROOT_SURFACE_ID",
    "PORTAL_SCOPE_DEFAULT_ID",
    "PORTAL_SHELL_COMPOSITION_SCHEMA",
    "PORTAL_SHELL_ENTRYPOINT_ID",
    "PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA",
    "PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA",
    "PORTAL_SHELL_REGION_INSPECTOR_SCHEMA",
    "PORTAL_SHELL_REGION_WORKBENCH_SCHEMA",
    "PORTAL_SHELL_REQUEST_SCHEMA",
    "PORTAL_SHELL_STATE_SCHEMA",
    "PORTAL_SURFACE_CATALOG_ENTRY_SCHEMA",
    "PORTAL_TOOL_REGISTRY_ENTRY_SCHEMA",
    "PortalScope",
    "PortalShellChrome",
    "PortalShellRequest",
    "PortalShellSelection",
    "PortalSurfaceCatalogEntry",
    "PortalToolLaunchDecision",
    "PortalToolRegistryEntry",
    "SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY",
    "SURFACE_POSTURE_WORKBENCH_PRIMARY",
    "SYSTEM_ACTIVITY_ROUTE",
    "SYSTEM_ACTIVITY_SURFACE_ID",
    "SYSTEM_OPERATIONAL_STATUS_ROUTE",
    "SYSTEM_OPERATIONAL_STATUS_SURFACE_ID",
    "SYSTEM_PROFILE_BASICS_ROUTE",
    "SYSTEM_PROFILE_BASICS_SURFACE_ID",
    "SYSTEM_ROOT_ROUTE",
    "SYSTEM_ROOT_SURFACE_ID",
    "TOOL_KIND_GENERAL",
    "TOOL_KIND_HOST_ALIAS",
    "TOOL_KIND_SERVICE",
    "TOOL_SURFACE_IDS",
    "UTILITIES_INTEGRATIONS_ROUTE",
    "UTILITIES_INTEGRATIONS_SURFACE_ID",
    "UTILITIES_ROOT_ROUTE",
    "UTILITIES_ROOT_SURFACE_ID",
    "UTILITIES_TOOL_EXPOSURE_ROUTE",
    "UTILITIES_TOOL_EXPOSURE_SURFACE_ID",
    "activity_icon_id_for_surface",
    "apply_surface_posture_to_composition",
    "build_portal_activity_dispatch_bodies",
    "build_portal_surface_catalog",
    "build_portal_tool_registry_entries",
    "build_shell_composition_payload",
    "canonical_route_for_surface",
    "foreground_region_for_surface",
    "inspector_collapsed_for_surface",
    "is_tool_surface",
    "map_surface_to_active_service",
    "requires_shell_state_machine",
    "resolve_portal_shell_request",
    "resolve_portal_surface",
    "resolve_portal_tool_launch",
    "resolve_portal_tool_registry_entry",
    "shell_composition_mode_for_surface",
    "surface_posture_for_surface",
    "surface_root_id",
]
