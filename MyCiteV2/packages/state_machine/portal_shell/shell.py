from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlencode

from MyCiteV2.packages.core.network_root_surface_query import normalize_network_surface_query

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
NETWORK_ROOT_SURFACE_ID = "network.root"
UTILITIES_ROOT_SURFACE_ID = "utilities.root"
UTILITIES_TOOL_EXPOSURE_SURFACE_ID = "utilities.tool_exposure"
UTILITIES_INTEGRATIONS_SURFACE_ID = "utilities.integrations"

AWS_CSM_TOOL_SURFACE_ID = "system.tools.aws_csm"
CTS_GIS_TOOL_SURFACE_ID = "system.tools.cts_gis"
FND_DCM_TOOL_SURFACE_ID = "system.tools.fnd_dcm"
FND_EBI_TOOL_SURFACE_ID = "system.tools.fnd_ebi"
WORKBENCH_UI_TOOL_SURFACE_ID = "system.tools.workbench_ui"

PORTAL_SHELL_ENTRYPOINT_ID = "portal.shell"
AWS_CSM_TOOL_ENTRYPOINT_ID = "portal.system.tools.aws_csm"
CTS_GIS_TOOL_ENTRYPOINT_ID = "portal.system.tools.cts_gis"
FND_DCM_TOOL_ENTRYPOINT_ID = "portal.system.tools.fnd_dcm"
FND_EBI_TOOL_ENTRYPOINT_ID = "portal.system.tools.fnd_ebi"
WORKBENCH_UI_TOOL_ENTRYPOINT_ID = "portal.system.tools.workbench_ui"

SYSTEM_ROOT_ROUTE = "/portal/system"
NETWORK_ROOT_ROUTE = "/portal/network"
UTILITIES_ROOT_ROUTE = "/portal/utilities"
UTILITIES_TOOL_EXPOSURE_ROUTE = "/portal/utilities/tool-exposure"
UTILITIES_INTEGRATIONS_ROUTE = "/portal/utilities/integrations"

AWS_CSM_TOOL_ROUTE = "/portal/system/tools/aws-csm"
CTS_GIS_TOOL_ROUTE = "/portal/system/tools/cts-gis"
FND_DCM_TOOL_ROUTE = "/portal/system/tools/fnd-dcm"
FND_EBI_TOOL_ROUTE = "/portal/system/tools/fnd-ebi"
WORKBENCH_UI_TOOL_ROUTE = "/portal/system/tools/workbench-ui"
FND_DCM_DEFAULT_SITE = "cuyahogavalleycountrysideconservancy.org"

SYSTEM_ANCHOR_FILE_KEY = "anthology"
SYSTEM_ACTIVITY_FILE_KEY = "activity"
SYSTEM_PROFILE_BASICS_FILE_KEY = "profile_basics"
SYSTEM_SANDBOX_QUERY_FILE_TOKEN = "sandbox"

PORTAL_SCOPE_DEFAULT_ID = "fnd"
SURFACE_POSTURE_WORKBENCH_PRIMARY = "workbench_primary"
SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY = "interface_panel_primary"
TOOL_KIND_GENERAL = "general_tool"
TOOL_KIND_SERVICE = "service_tool"
TOOL_KIND_HOST_ALIAS = "host_alias_tool"

FOCUS_LEVEL_SANDBOX = "sandbox"
FOCUS_LEVEL_FILE = "file"
FOCUS_LEVEL_DATUM = "datum"
FOCUS_LEVEL_OBJECT = "object"
FOCUS_LEVELS = (
    FOCUS_LEVEL_SANDBOX,
    FOCUS_LEVEL_FILE,
    FOCUS_LEVEL_DATUM,
    FOCUS_LEVEL_OBJECT,
)
FOCUS_LEVEL_INDEX = {level: index for index, level in enumerate(FOCUS_LEVELS)}

VERB_NAVIGATE = "navigate"
VERB_INVESTIGATE = "investigate"
VERB_MEDIATE = "mediate"
VERB_MANIPULATE = "manipulate"
PORTAL_SHELL_VERBS = (
    VERB_NAVIGATE,
    VERB_INVESTIGATE,
    VERB_MEDIATE,
    VERB_MANIPULATE,
)

TRANSITION_ENTER_SURFACE = "enter_surface"
TRANSITION_FOCUS_FILE = "focus_file"
TRANSITION_FOCUS_DATUM = "focus_datum"
TRANSITION_FOCUS_OBJECT = "focus_object"
TRANSITION_BACK_OUT = "back_out"
TRANSITION_SET_VERB = "set_verb"
TRANSITION_OPEN_INTERFACE_PANEL = "open_interface_panel"
TRANSITION_CLOSE_INTERFACE_PANEL = "close_interface_panel"
PORTAL_SHELL_TRANSITIONS = (
    TRANSITION_ENTER_SURFACE,
    TRANSITION_FOCUS_FILE,
    TRANSITION_FOCUS_DATUM,
    TRANSITION_FOCUS_OBJECT,
    TRANSITION_BACK_OUT,
    TRANSITION_SET_VERB,
    TRANSITION_OPEN_INTERFACE_PANEL,
    TRANSITION_CLOSE_INTERFACE_PANEL,
)

ROOT_SURFACE_IDS = frozenset(
    {
        SYSTEM_ROOT_SURFACE_ID,
        NETWORK_ROOT_SURFACE_ID,
        UTILITIES_ROOT_SURFACE_ID,
    }
)
TOOL_SURFACE_IDS = frozenset(
    {
        AWS_CSM_TOOL_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_DCM_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
        WORKBENCH_UI_TOOL_SURFACE_ID,
    }
)
SYSTEM_SURFACE_IDS = frozenset({SYSTEM_ROOT_SURFACE_ID, *TOOL_SURFACE_IDS})
NETWORK_SURFACE_IDS = frozenset({NETWORK_ROOT_SURFACE_ID})
UTILITIES_SURFACE_IDS = frozenset(
    {
        UTILITIES_ROOT_SURFACE_ID,
        UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        UTILITIES_INTEGRATIONS_SURFACE_ID,
    }
)
REDUCER_OWNED_SURFACE_IDS = frozenset(
    {
        SYSTEM_ROOT_SURFACE_ID,
        CTS_GIS_TOOL_SURFACE_ID,
        FND_EBI_TOOL_SURFACE_ID,
    }
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_slug(value: object) -> str:
    return _as_text(value).lower().replace("-", "_").replace(" ", "_")


def _require_schema(payload: dict[str, Any], *, expected: str, field_name: str) -> None:
    schema = _as_text(payload.get("schema"))
    if schema != expected:
        raise ValueError(f"{field_name} must be {expected}")


def _normalize_surface_query(value: object, *, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping or null")
    out: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _as_text(raw_key)
        if not key:
            raise ValueError(f"{field_name} keys must be non-empty")
        token = _as_text(raw_value)
        if token:
            out[key] = token
    return out


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
        item = _normalize_slug(raw_item)
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
    control_panel_collapsed: bool = False
    interface_panel_open: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.control_panel_collapsed, bool):
            raise ValueError("shell_chrome.control_panel_collapsed must be a bool")
        if not isinstance(self.interface_panel_open, bool):
            raise ValueError("shell_chrome.interface_panel_open must be a bool")

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_panel_collapsed": self.control_panel_collapsed,
            "interface_panel_open": self.interface_panel_open,
        }

    @classmethod
    def from_value(cls, payload: dict[str, Any] | None) -> "PortalShellChrome":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("shell_chrome must be a dict or null")
        return cls(
            control_panel_collapsed=payload.get("control_panel_collapsed") is True,
            interface_panel_open=payload.get("interface_panel_open") is True,
        )


@dataclass(frozen=True)
class PortalFocusSegment:
    level: str
    id: str

    def __post_init__(self) -> None:
        level = _normalize_slug(self.level)
        token = _as_text(self.id)
        if level not in FOCUS_LEVEL_INDEX:
            raise ValueError("focus_segment.level is invalid")
        if not token:
            raise ValueError("focus_segment.id is required")
        object.__setattr__(self, "level", level)
        object.__setattr__(self, "id", token)

    def to_dict(self) -> dict[str, str]:
        return {"level": self.level, "id": self.id}

    @classmethod
    def from_value(cls, payload: dict[str, Any] | "PortalFocusSegment") -> "PortalFocusSegment":
        if isinstance(payload, cls):
            return payload
        if not isinstance(payload, dict):
            raise ValueError("focus_segment must be a dict")
        return cls(level=payload.get("level"), id=payload.get("id"))


def _normalize_focus_path(
    value: object,
    *,
    scope_id: str,
) -> tuple[PortalFocusSegment, ...]:
    if value is None:
        raw_segments: list[Any] = []
    elif isinstance(value, (list, tuple)):
        raw_segments = list(value)
    else:
        raise ValueError("portal_shell_state.focus_path must be a list, tuple, or null")

    segments: list[PortalFocusSegment] = []
    seen_levels: set[str] = set()
    for raw_segment in raw_segments:
        segment = PortalFocusSegment.from_value(raw_segment)
        if segment.level in seen_levels:
            continue
        segments.append(segment)
        seen_levels.add(segment.level)

    if not segments or segments[0].level != FOCUS_LEVEL_SANDBOX:
        segments.insert(0, PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=scope_id))
    else:
        segments[0] = PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=segments[0].id or scope_id)

    normalized: list[PortalFocusSegment] = []
    expected_index = 0
    for segment in sorted(segments, key=lambda item: FOCUS_LEVEL_INDEX[item.level]):
        if FOCUS_LEVEL_INDEX[segment.level] != expected_index:
            break
        normalized.append(segment)
        expected_index += 1
    return tuple(normalized)


def _subject_from_segment(segment: PortalFocusSegment | None) -> dict[str, str] | None:
    if segment is None:
        return None
    return segment.to_dict()


def _normalize_subject(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, PortalFocusSegment):
        return value.to_dict()
    if isinstance(value, dict):
        segment = PortalFocusSegment.from_value(value)
        return segment.to_dict()
    raise ValueError("focus_subject and mediation_subject must be dicts or null")


@dataclass(frozen=True)
class PortalShellState:
    active_surface_id: str
    focus_path: tuple[PortalFocusSegment | dict[str, Any], ...]
    focus_subject: dict[str, str] | None = None
    mediation_subject: dict[str, str] | None = None
    verb: str = VERB_NAVIGATE
    chrome: PortalShellChrome = field(default_factory=PortalShellChrome)
    schema: str = field(default=PORTAL_SHELL_STATE_SCHEMA, init=False)

    def __post_init__(self) -> None:
        active_surface_id = _as_text(self.active_surface_id) or SYSTEM_ROOT_SURFACE_ID
        if self.verb not in PORTAL_SHELL_VERBS:
            raise ValueError("portal_shell_state.verb is invalid")
        chrome = self.chrome if isinstance(self.chrome, PortalShellChrome) else PortalShellChrome.from_value(self.chrome)
        scope_id = PORTAL_SCOPE_DEFAULT_ID
        if self.focus_path:
            first_segment = self.focus_path[0]
            if isinstance(first_segment, PortalFocusSegment):
                scope_id = first_segment.id or PORTAL_SCOPE_DEFAULT_ID
            elif isinstance(first_segment, dict):
                scope_id = _as_text(first_segment.get("id")) or PORTAL_SCOPE_DEFAULT_ID
        focus_path = _normalize_focus_path(self.focus_path, scope_id=scope_id)
        if not focus_path:
            raise ValueError("portal_shell_state.focus_path must include sandbox focus")
        focus_subject = _normalize_subject(self.focus_subject) or _subject_from_segment(focus_path[-1])
        mediation_subject = _normalize_subject(self.mediation_subject)
        object.__setattr__(self, "active_surface_id", active_surface_id)
        object.__setattr__(self, "focus_path", focus_path)
        object.__setattr__(self, "focus_subject", focus_subject)
        object.__setattr__(self, "mediation_subject", mediation_subject)
        object.__setattr__(self, "chrome", chrome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "active_surface_id": self.active_surface_id,
            "focus_path": [segment.to_dict() for segment in self.focus_path],
            "focus_subject": dict(self.focus_subject) if isinstance(self.focus_subject, dict) else None,
            "mediation_subject": dict(self.mediation_subject) if isinstance(self.mediation_subject, dict) else None,
            "verb": self.verb,
            "chrome": self.chrome.to_dict(),
        }

    @classmethod
    def from_value(
        cls,
        payload: dict[str, Any] | "PortalShellState" | None,
        *,
        portal_scope: PortalScope | None = None,
        fallback_surface_id: str = SYSTEM_ROOT_SURFACE_ID,
    ) -> "PortalShellState":
        if isinstance(payload, cls):
            return payload
        if payload is None:
            return initial_portal_shell_state(surface_id=fallback_surface_id, portal_scope=portal_scope or PortalScope())
        if not isinstance(payload, dict):
            raise ValueError("portal_shell_state must be a dict or null")
        if _as_text(payload.get("schema")) not in {"", PORTAL_SHELL_STATE_SCHEMA}:
            raise ValueError(f"portal_shell_state.schema must be {PORTAL_SHELL_STATE_SCHEMA}")
        scope_id = (portal_scope or PortalScope()).scope_id
        focus_path = _normalize_focus_path(payload.get("focus_path"), scope_id=scope_id)
        return cls(
            active_surface_id=payload.get("active_surface_id") or fallback_surface_id,
            focus_path=focus_path,
            focus_subject=_normalize_subject(payload.get("focus_subject")) or _subject_from_segment(focus_path[-1]),
            mediation_subject=_normalize_subject(payload.get("mediation_subject")),
            verb=_as_text(payload.get("verb")) or VERB_NAVIGATE,
            chrome=PortalShellChrome.from_value(payload.get("chrome")),
        )


@dataclass(frozen=True)
class PortalShellTransition:
    kind: str
    surface_id: str = ""
    file_key: str = ""
    datum_id: str = ""
    object_id: str = ""
    verb: str = ""

    def __post_init__(self) -> None:
        kind = _normalize_slug(self.kind)
        verb = _normalize_slug(self.verb)
        if kind not in PORTAL_SHELL_TRANSITIONS:
            raise ValueError("portal_shell_transition.kind is invalid")
        if verb and verb not in PORTAL_SHELL_VERBS:
            raise ValueError("portal_shell_transition.verb is invalid")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "surface_id", _as_text(self.surface_id))
        object.__setattr__(self, "file_key", _as_text(self.file_key))
        object.__setattr__(self, "datum_id", _as_text(self.datum_id))
        object.__setattr__(self, "object_id", _as_text(self.object_id))
        object.__setattr__(self, "verb", verb)

    def to_dict(self) -> dict[str, Any]:
        payload = {"kind": self.kind}
        if self.surface_id:
            payload["surface_id"] = self.surface_id
        if self.file_key:
            payload["file_key"] = self.file_key
        if self.datum_id:
            payload["datum_id"] = self.datum_id
        if self.object_id:
            payload["object_id"] = self.object_id
        if self.verb:
            payload["verb"] = self.verb
        return payload

    @classmethod
    def from_value(cls, payload: dict[str, Any] | "PortalShellTransition" | None) -> "PortalShellTransition | None":
        if payload is None:
            return None
        if isinstance(payload, cls):
            return payload
        if not isinstance(payload, dict):
            raise ValueError("portal_shell_transition must be a dict or null")
        return cls(
            kind=payload.get("kind"),
            surface_id=payload.get("surface_id") or payload.get("requested_surface_id") or "",
            file_key=payload.get("file_key") or "",
            datum_id=payload.get("datum_id") or "",
            object_id=payload.get("object_id") or "",
            verb=payload.get("verb") or "",
        )


@dataclass(frozen=True)
class PortalShellRequest:
    requested_surface_id: str = SYSTEM_ROOT_SURFACE_ID
    portal_scope: PortalScope = field(default_factory=PortalScope)
    shell_state: PortalShellState | None = None
    transition: PortalShellTransition | None = None
    surface_query: dict[str, str] = field(default_factory=dict)
    schema: str = field(default=PORTAL_SHELL_REQUEST_SCHEMA, init=False)

    def __post_init__(self) -> None:
        requested_surface_id = _as_text(self.requested_surface_id) or SYSTEM_ROOT_SURFACE_ID
        portal_scope = self.portal_scope if isinstance(self.portal_scope, PortalScope) else PortalScope.from_value(self.portal_scope)
        shell_state = (
            self.shell_state
            if isinstance(self.shell_state, PortalShellState) or self.shell_state is None
            else PortalShellState.from_value(self.shell_state, portal_scope=portal_scope, fallback_surface_id=requested_surface_id)
        )
        transition = (
            self.transition
            if isinstance(self.transition, PortalShellTransition) or self.transition is None
            else PortalShellTransition.from_value(self.transition)
        )
        surface_query = _normalize_surface_query(
            self.surface_query,
            field_name="portal_shell_request.surface_query",
        )
        object.__setattr__(self, "requested_surface_id", requested_surface_id)
        object.__setattr__(self, "portal_scope", portal_scope)
        object.__setattr__(self, "shell_state", shell_state)
        object.__setattr__(self, "transition", transition)
        object.__setattr__(self, "surface_query", surface_query)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": self.schema,
            "requested_surface_id": self.requested_surface_id,
            "portal_scope": self.portal_scope.to_dict(),
        }
        if self.shell_state is not None:
            payload["shell_state"] = self.shell_state.to_dict()
        if self.transition is not None:
            payload["transition"] = self.transition.to_dict()
        if self.surface_query:
            payload["surface_query"] = dict(self.surface_query)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PortalShellRequest":
        if payload is None:
            return cls()
        if not isinstance(payload, dict):
            raise ValueError("portal_shell_request must be a dict")
        _require_schema(payload, expected=PORTAL_SHELL_REQUEST_SCHEMA, field_name="portal_shell_request.schema")
        portal_scope = PortalScope.from_value(payload.get("portal_scope"))
        requested_surface_id = payload.get("requested_surface_id") or SYSTEM_ROOT_SURFACE_ID
        return cls(
            requested_surface_id=requested_surface_id,
            portal_scope=portal_scope,
            shell_state=PortalShellState.from_value(
                payload.get("shell_state"),
                portal_scope=portal_scope,
                fallback_surface_id=requested_surface_id,
            )
            if payload.get("shell_state") is not None
            else None,
            transition=PortalShellTransition.from_value(payload.get("transition")),
            surface_query=_normalize_surface_query(
                payload.get("surface_query"),
                field_name="portal_shell_request.surface_query",
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
    default_workbench_visible: bool = False
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
        object.__setattr__(self, "default_workbench_visible", bool(self.default_workbench_visible))

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
            "default_workbench_visible": self.default_workbench_visible,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PortalShellResolution:
    requested_surface_id: str
    active_surface_id: str
    selection_status: str
    allowed: bool
    reducer_owned: bool
    shell_state: PortalShellState | None = None
    canonical_route: str = ""
    canonical_query: dict[str, str] = field(default_factory=dict)
    canonical_url: str = ""
    reason_code: str = ""
    reason_message: str = ""


def build_portal_surface_catalog() -> tuple[PortalSurfaceCatalogEntry, ...]:
    return (
        PortalSurfaceCatalogEntry(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            label="System",
            route=SYSTEM_ROOT_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="system_workspace",
            page_owner="system",
            default_surface=True,
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
            surface_id=AWS_CSM_TOOL_SURFACE_ID,
            label="AWS-CSM",
            route=AWS_CSM_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="aws_csm",
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
            surface_id=FND_DCM_TOOL_SURFACE_ID,
            label="FND-DCM",
            route=FND_DCM_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="fnd_dcm",
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
        PortalSurfaceCatalogEntry(
            surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            label="Workbench UI",
            route=WORKBENCH_UI_TOOL_ROUTE,
            root_surface_id=SYSTEM_ROOT_SURFACE_ID,
            surface_kind="tool_surface",
            page_owner="system",
            tool_id="workbench_ui",
        ),
    )


def build_portal_tool_registry_entries() -> tuple[PortalToolRegistryEntry, ...]:
    return (
        PortalToolRegistryEntry(
            tool_id="aws_csm",
            label="AWS-CSM",
            surface_id=AWS_CSM_TOOL_SURFACE_ID,
            entrypoint_id=AWS_CSM_TOOL_ENTRYPOINT_ID,
            route=AWS_CSM_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("fnd_peripheral_routing",),
            summary="Unified domain gallery with mailbox onboarding and newsletter state.",
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
            tool_id="fnd_dcm",
            label="FND-DCM",
            surface_id=FND_DCM_TOOL_SURFACE_ID,
            entrypoint_id=FND_DCM_TOOL_ENTRYPOINT_ID,
            route=FND_DCM_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("hosted_site_manifest_visibility", "fnd_peripheral_routing"),
            summary="Hosted manifest inspection and collection normalization.",
        ),
        PortalToolRegistryEntry(
            tool_id="fnd_ebi",
            label="FND-EBI",
            surface_id=FND_EBI_TOOL_SURFACE_ID,
            entrypoint_id=FND_EBI_TOOL_ENTRYPOINT_ID,
            route=FND_EBI_TOOL_ROUTE,
            tool_kind=TOOL_KIND_SERVICE,
            surface_posture=SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("hosted_site_visibility", "fnd_peripheral_routing"),
            summary="Hosted site operational visibility.",
        ),
        PortalToolRegistryEntry(
            tool_id="workbench_ui",
            label="Workbench UI",
            surface_id=WORKBENCH_UI_TOOL_SURFACE_ID,
            entrypoint_id=WORKBENCH_UI_TOOL_ENTRYPOINT_ID,
            route=WORKBENCH_UI_TOOL_ROUTE,
            tool_kind=TOOL_KIND_GENERAL,
            surface_posture=SURFACE_POSTURE_WORKBENCH_PRIMARY,
            read_write_posture="read-only",
            required_capabilities=("datum_recognition",),
            default_enabled=True,
            default_workbench_visible=True,
            summary="Read-only SQL datum grid with additive directive-overlay inspection.",
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
    return _as_text(surface_id) in REDUCER_OWNED_SURFACE_IDS


def default_focus_path(*, scope_id: str, include_anchor_file: bool) -> tuple[PortalFocusSegment, ...]:
    segments = [PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=scope_id or PORTAL_SCOPE_DEFAULT_ID)]
    if include_anchor_file:
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=SYSTEM_ANCHOR_FILE_KEY))
    return tuple(segments)


def initial_portal_shell_state(
    *,
    surface_id: str,
    portal_scope: PortalScope | dict[str, Any],
) -> PortalShellState:
    normalized_scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    focus_path = default_focus_path(
        scope_id=normalized_scope.scope_id,
        include_anchor_file=requires_shell_state_machine(surface_id),
    )
    base_state = PortalShellState(
        active_surface_id=surface_id,
        focus_path=focus_path,
        focus_subject=_subject_from_segment(focus_path[-1]),
        mediation_subject=None,
        verb=VERB_NAVIGATE,
        chrome=PortalShellChrome(control_panel_collapsed=False, interface_panel_open=False),
    )
    return canonicalize_portal_shell_state(
        base_state,
        active_surface_id=surface_id,
        portal_scope=normalized_scope,
        seed_anchor_file=True,
    )


def focus_level_for_shell_state(shell_state: PortalShellState | dict[str, Any] | None) -> str:
    if shell_state is None:
        return FOCUS_LEVEL_SANDBOX
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    return state.focus_path[-1].level if state.focus_path else FOCUS_LEVEL_SANDBOX


def segment_id_for_level(shell_state: PortalShellState | dict[str, Any] | None, *, level: str) -> str:
    if shell_state is None:
        return ""
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    for segment in state.focus_path:
        if segment.level == level:
            return segment.id
    return ""


def _focus_path_contains_subject(focus_path: tuple[PortalFocusSegment, ...], subject: dict[str, str] | None) -> bool:
    if not isinstance(subject, dict):
        return False
    subject_level = _normalize_slug(subject.get("level"))
    subject_id = _as_text(subject.get("id"))
    if subject_level not in FOCUS_LEVEL_INDEX or not subject_id:
        return False
    for segment in focus_path:
        if segment.level == subject_level and segment.id == subject_id:
            return True
    return False


def _state_with(
    state: PortalShellState,
    *,
    active_surface_id: str | None = None,
    focus_path: tuple[PortalFocusSegment, ...] | None = None,
    focus_subject: dict[str, str] | None | object = ...,
    mediation_subject: dict[str, str] | None | object = ...,
    verb: str | None = None,
    chrome: PortalShellChrome | None = None,
) -> PortalShellState:
    next_focus_path = focus_path if focus_path is not None else state.focus_path
    next_focus_subject = state.focus_subject if focus_subject is ... else focus_subject
    next_mediation_subject = state.mediation_subject if mediation_subject is ... else mediation_subject
    return PortalShellState(
        active_surface_id=active_surface_id or state.active_surface_id,
        focus_path=next_focus_path,
        focus_subject=next_focus_subject,
        mediation_subject=next_mediation_subject,
        verb=verb or state.verb,
        chrome=chrome or state.chrome,
    )


def _subject_for_level(focus_path: tuple[PortalFocusSegment, ...], *, level: str) -> dict[str, str] | None:
    for segment in focus_path:
        if segment.level == level:
            return segment.to_dict()
    return None


def _with_focus_path(
    shell_state: PortalShellState,
    *,
    active_surface_id: str,
    portal_scope: PortalScope,
    focus_path: tuple[PortalFocusSegment, ...],
) -> PortalShellState:
    next_focus_subject = _subject_from_segment(focus_path[-1]) if focus_path else None
    next_mediation_subject = shell_state.mediation_subject
    if next_mediation_subject and not _focus_path_contains_subject(focus_path, next_mediation_subject):
        next_mediation_subject = None
    next_verb = shell_state.verb
    next_chrome = shell_state.chrome
    if active_surface_id == SYSTEM_ROOT_SURFACE_ID and next_mediation_subject is None and next_verb == VERB_MEDIATE:
        next_verb = VERB_NAVIGATE
        next_chrome = PortalShellChrome(
            control_panel_collapsed=shell_state.chrome.control_panel_collapsed,
            interface_panel_open=False,
        )
    return PortalShellState(
        active_surface_id=active_surface_id,
        focus_path=focus_path,
        focus_subject=next_focus_subject,
        mediation_subject=next_mediation_subject,
        verb=next_verb,
        chrome=next_chrome,
    )


def canonicalize_portal_shell_state(
    shell_state: PortalShellState | dict[str, Any] | None,
    *,
    active_surface_id: str,
    portal_scope: PortalScope,
    seed_anchor_file: bool,
) -> PortalShellState:
    state = PortalShellState.from_value(
        shell_state,
        portal_scope=portal_scope,
        fallback_surface_id=active_surface_id,
    )
    focus_path = _normalize_focus_path(state.focus_path, scope_id=portal_scope.scope_id)
    if seed_anchor_file and len(focus_path) == 1:
        focus_path = default_focus_path(scope_id=portal_scope.scope_id, include_anchor_file=True)
    focus_subject = _subject_from_segment(focus_path[-1])
    mediation_subject = state.mediation_subject if _focus_path_contains_subject(focus_path, state.mediation_subject) else None
    verb = state.verb
    chrome = state.chrome

    if is_tool_surface(active_surface_id):
        mediation_subject = mediation_subject or focus_subject
        verb = VERB_MEDIATE
        chrome = PortalShellChrome(
            control_panel_collapsed=chrome.control_panel_collapsed,
            interface_panel_open=True,
        )
    elif active_surface_id == SYSTEM_ROOT_SURFACE_ID:
        if verb == VERB_MEDIATE:
            if mediation_subject is None:
                verb = VERB_NAVIGATE
                chrome = PortalShellChrome(
                    control_panel_collapsed=chrome.control_panel_collapsed,
                    interface_panel_open=False,
                )
            else:
                chrome = PortalShellChrome(
                    control_panel_collapsed=chrome.control_panel_collapsed,
                    interface_panel_open=True,
                )
        else:
            mediation_subject = None
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=False,
            )

    return PortalShellState(
        active_surface_id=active_surface_id,
        focus_path=focus_path,
        focus_subject=focus_subject,
        mediation_subject=mediation_subject,
        verb=verb,
        chrome=chrome,
    )


def reduce_portal_shell_state(
    *,
    active_surface_id: str,
    portal_scope: PortalScope | dict[str, Any],
    current_state: PortalShellState | dict[str, Any] | None,
    transition: PortalShellTransition | dict[str, Any] | None,
    seed_anchor_file: bool,
) -> PortalShellState:
    normalized_scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    state = canonicalize_portal_shell_state(
        current_state,
        active_surface_id=active_surface_id,
        portal_scope=normalized_scope,
        seed_anchor_file=seed_anchor_file,
    )
    normalized_transition = PortalShellTransition.from_value(transition)
    if normalized_transition is None:
        return canonicalize_portal_shell_state(
            state,
            active_surface_id=active_surface_id,
            portal_scope=normalized_scope,
            seed_anchor_file=seed_anchor_file,
        )

    focus_path = list(state.focus_path)
    verb = state.verb
    mediation_subject = state.mediation_subject
    chrome = state.chrome

    if normalized_transition.kind == TRANSITION_ENTER_SURFACE:
        return canonicalize_portal_shell_state(
            state,
            active_surface_id=active_surface_id,
            portal_scope=normalized_scope,
            seed_anchor_file=seed_anchor_file,
        )

    if normalized_transition.kind == TRANSITION_FOCUS_FILE:
        next_file_key = _as_text(normalized_transition.file_key)
        if next_file_key == SYSTEM_SANDBOX_QUERY_FILE_TOKEN:
            focus_path = [PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id)]
        else:
            if not next_file_key:
                next_file_key = SYSTEM_ANCHOR_FILE_KEY
            focus_path = [
                PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id),
                PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=next_file_key),
            ]
    elif normalized_transition.kind == TRANSITION_FOCUS_DATUM:
        file_key = normalized_transition.file_key or segment_id_for_level(state, level=FOCUS_LEVEL_FILE) or SYSTEM_ANCHOR_FILE_KEY
        focus_path = [
            PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id),
            PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=file_key),
        ]
        if normalized_transition.datum_id:
            focus_path.append(PortalFocusSegment(level=FOCUS_LEVEL_DATUM, id=normalized_transition.datum_id))
    elif normalized_transition.kind == TRANSITION_FOCUS_OBJECT:
        file_key = normalized_transition.file_key or segment_id_for_level(state, level=FOCUS_LEVEL_FILE) or SYSTEM_ANCHOR_FILE_KEY
        datum_id = normalized_transition.datum_id or segment_id_for_level(state, level=FOCUS_LEVEL_DATUM)
        focus_path = [
            PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=normalized_scope.scope_id),
            PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=file_key),
        ]
        if datum_id:
            focus_path.append(PortalFocusSegment(level=FOCUS_LEVEL_DATUM, id=datum_id))
        if normalized_transition.object_id:
            focus_path.append(PortalFocusSegment(level=FOCUS_LEVEL_OBJECT, id=normalized_transition.object_id))
    elif normalized_transition.kind == TRANSITION_BACK_OUT:
        if len(focus_path) > 1:
            focus_path = focus_path[:-1]
        else:
            focus_path = focus_path[:]
    elif normalized_transition.kind == TRANSITION_SET_VERB:
        verb = normalized_transition.verb or VERB_NAVIGATE
        if verb == VERB_MEDIATE:
            mediation_subject = _subject_from_segment(focus_path[-1])
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=True,
            )
        else:
            mediation_subject = None
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=False,
            )
    elif normalized_transition.kind == TRANSITION_OPEN_INTERFACE_PANEL:
        if active_surface_id == SYSTEM_ROOT_SURFACE_ID:
            mediation_subject = _subject_from_segment(focus_path[-1])
            verb = VERB_MEDIATE
        chrome = PortalShellChrome(
            control_panel_collapsed=chrome.control_panel_collapsed,
            interface_panel_open=True,
        )
    elif normalized_transition.kind == TRANSITION_CLOSE_INTERFACE_PANEL:
        if active_surface_id == SYSTEM_ROOT_SURFACE_ID:
            mediation_subject = None
            verb = VERB_NAVIGATE
            chrome = PortalShellChrome(
                control_panel_collapsed=chrome.control_panel_collapsed,
                interface_panel_open=False,
            )

    next_state = PortalShellState(
        active_surface_id=active_surface_id,
        focus_path=tuple(focus_path),
        focus_subject=_subject_from_segment(focus_path[-1]) if focus_path else _subject_for_level(tuple(focus_path), level=FOCUS_LEVEL_SANDBOX),
        mediation_subject=mediation_subject,
        verb=verb,
        chrome=chrome,
    )
    return canonicalize_portal_shell_state(
        next_state,
        active_surface_id=active_surface_id,
        portal_scope=normalized_scope,
        seed_anchor_file=seed_anchor_file,
    )


def canonical_query_for_shell_state(
    shell_state: PortalShellState | dict[str, Any] | None,
    *,
    surface_id: str,
) -> dict[str, str]:
    if not requires_shell_state_machine(surface_id):
        return {}
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    file_id = segment_id_for_level(state, level=FOCUS_LEVEL_FILE)
    query: dict[str, str] = {
        "file": file_id or SYSTEM_SANDBOX_QUERY_FILE_TOKEN,
        "verb": state.verb,
    }
    datum_id = segment_id_for_level(state, level=FOCUS_LEVEL_DATUM)
    object_id = segment_id_for_level(state, level=FOCUS_LEVEL_OBJECT)
    if datum_id:
        query["datum"] = datum_id
    if object_id:
        query["object"] = object_id
    return query


def canonical_query_for_surface_query(
    surface_query: Mapping[str, Any] | None,
    *,
    surface_id: str,
) -> dict[str, str]:
    if surface_id == NETWORK_ROOT_SURFACE_ID:
        if surface_query is not None and not isinstance(surface_query, Mapping):
            raise ValueError("portal_shell_request.surface_query must be a mapping or null")
        query, _ = normalize_network_surface_query(surface_query)
        return query
    normalized = _normalize_surface_query(
        surface_query,
        field_name="portal_shell_request.surface_query",
    )
    if surface_id == AWS_CSM_TOOL_SURFACE_ID:
        query = {"view": "domains"}
        if _as_text(normalized.get("domain")):
            query["domain"] = _as_text(normalized.get("domain")).lower()
        if _as_text(normalized.get("profile")):
            query["profile"] = _as_text(normalized.get("profile"))
        section = _as_text(normalized.get("section")).lower()
        if section in {"users", "onboarding", "newsletter"}:
            query["section"] = section
        return query
    if surface_id == FND_DCM_TOOL_SURFACE_ID:
        view = _as_text(normalized.get("view")).lower()
        if view not in {"overview", "pages", "collections", "issues"}:
            view = "overview"
        query = {
            "site": _as_text(normalized.get("site")).lower() or FND_DCM_DEFAULT_SITE,
            "view": view,
        }
        if view == "pages" and _as_text(normalized.get("page")):
            query["page"] = _as_text(normalized.get("page"))
        if view == "collections" and _as_text(normalized.get("collection")):
            query["collection"] = _as_text(normalized.get("collection"))
        return query
    if surface_id == WORKBENCH_UI_TOOL_SURFACE_ID:
        query: dict[str, str] = {}
        document_id = _as_text(normalized.get("document"))
        if document_id:
            query["document"] = document_id
        document_filter = _as_text(normalized.get("document_filter"))
        if document_filter:
            query["document_filter"] = document_filter
        document_sort_key = _as_text(normalized.get("document_sort")).lower()
        if document_sort_key in {"document_id", "document_name", "source_kind", "row_count", "version_hash"}:
            query["document_sort"] = document_sort_key
        document_sort_direction = _as_text(normalized.get("document_dir")).lower()
        if document_sort_direction in {"asc", "desc"}:
            query["document_dir"] = document_sort_direction
        text_filter = _as_text(normalized.get("filter"))
        if text_filter:
            query["filter"] = text_filter
        sort_key = _as_text(normalized.get("sort")).lower()
        if sort_key in {
            "datum_address",
            "layer",
            "value_group",
            "iteration",
            "labels",
            "relation",
            "object_ref",
            "hyphae_hash",
        }:
            query["sort"] = sort_key
        sort_direction = _as_text(normalized.get("dir")).lower()
        if sort_direction in {"asc", "desc"}:
            query["dir"] = sort_direction
        group_mode = _as_text(normalized.get("group")).lower()
        if group_mode in {"flat", "layer", "layer_value_group"}:
            query["group"] = group_mode
        workbench_lens = _as_text(normalized.get("workbench_lens")).lower()
        if workbench_lens in {"interpreted", "raw"}:
            query["workbench_lens"] = workbench_lens
        source_visibility = _as_text(normalized.get("source")).lower()
        if source_visibility in {"show", "hide"}:
            query["source"] = source_visibility
        overlay = _as_text(normalized.get("overlay")).lower()
        if overlay in {"show", "hide"}:
            query["overlay"] = overlay
        row_id = _as_text(normalized.get("row"))
        if row_id:
            query["row"] = row_id
        return query
    return {}


def build_canonical_url(*, surface_id: str, query: Mapping[str, str] | None = None) -> str:
    route = canonical_route_for_surface(surface_id)
    filtered = {key: value for key, value in dict(query or {}).items() if _as_text(value)}
    if not filtered:
        return route
    return f"{route}?{urlencode(filtered)}"


def build_portal_shell_state_from_query(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    query: Mapping[str, Any] | None,
) -> PortalShellState | None:
    if not requires_shell_state_machine(surface_id):
        return None
    params = dict(query or {})
    file_token = _as_text(params.get("file"))
    verb = _normalize_slug(params.get("verb")) or (VERB_MEDIATE if is_tool_surface(surface_id) else VERB_NAVIGATE)
    segments: list[PortalFocusSegment] = [PortalFocusSegment(level=FOCUS_LEVEL_SANDBOX, id=portal_scope.scope_id)]
    if file_token and file_token != SYSTEM_SANDBOX_QUERY_FILE_TOKEN:
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=file_token))
    elif not file_token:
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=SYSTEM_ANCHOR_FILE_KEY))
    datum_id = _as_text(params.get("datum"))
    object_id = _as_text(params.get("object"))
    if datum_id:
        if len(segments) == 1:
            segments.append(PortalFocusSegment(level=FOCUS_LEVEL_FILE, id=SYSTEM_ANCHOR_FILE_KEY))
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_DATUM, id=datum_id))
    if object_id:
        if not datum_id:
            return canonicalize_portal_shell_state(
                PortalShellState(
                    active_surface_id=surface_id,
                    focus_path=tuple(segments),
                    focus_subject=_subject_from_segment(segments[-1]),
                    mediation_subject=None,
                    verb=VERB_NAVIGATE,
                ),
                active_surface_id=surface_id,
                portal_scope=portal_scope,
                seed_anchor_file=True,
            )
        segments.append(PortalFocusSegment(level=FOCUS_LEVEL_OBJECT, id=object_id))
    base_state = PortalShellState(
        active_surface_id=surface_id,
        focus_path=tuple(segments),
        focus_subject=_subject_from_segment(segments[-1]),
        mediation_subject=_subject_from_segment(segments[-1]) if verb == VERB_MEDIATE else None,
        verb=verb,
        chrome=PortalShellChrome(interface_panel_open=verb == VERB_MEDIATE),
    )
    return canonicalize_portal_shell_state(
        base_state,
        active_surface_id=surface_id,
        portal_scope=portal_scope,
        seed_anchor_file=True,
    )


def build_portal_shell_request_payload(
    *,
    requested_surface_id: str,
    portal_scope: PortalScope | dict[str, Any] | None,
    shell_state: PortalShellState | dict[str, Any] | None = None,
    transition: PortalShellTransition | dict[str, Any] | None = None,
    surface_query: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    state = (
        shell_state
        if isinstance(shell_state, PortalShellState) or shell_state is None
        else PortalShellState.from_value(shell_state, portal_scope=scope, fallback_surface_id=requested_surface_id)
    )
    normalized_transition = (
        transition
        if isinstance(transition, PortalShellTransition) or transition is None
        else PortalShellTransition.from_value(transition)
    )
    return PortalShellRequest(
        requested_surface_id=requested_surface_id,
        portal_scope=scope,
        shell_state=state,
        transition=normalized_transition,
        surface_query=_normalize_surface_query(
            surface_query,
            field_name="portal_shell_request.surface_query",
        ),
    ).to_dict()


def resolve_portal_shell_request(request: PortalShellRequest | dict[str, Any] | None) -> PortalShellResolution:
    normalized_request = request if isinstance(request, PortalShellRequest) else PortalShellRequest.from_dict(request)
    requested_surface_id = normalized_request.requested_surface_id
    surface_entry = resolve_portal_surface(requested_surface_id)
    if surface_entry is None or not surface_entry.launchable:
        fallback_state = initial_portal_shell_state(surface_id=SYSTEM_ROOT_SURFACE_ID, portal_scope=normalized_request.portal_scope)
        fallback_query = canonical_query_for_shell_state(fallback_state, surface_id=SYSTEM_ROOT_SURFACE_ID)
        return PortalShellResolution(
            requested_surface_id=requested_surface_id,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            selection_status="unknown",
            allowed=False,
            reducer_owned=True,
            shell_state=fallback_state,
            canonical_route=SYSTEM_ROOT_ROUTE,
            canonical_query=fallback_query,
            canonical_url=build_canonical_url(surface_id=SYSTEM_ROOT_SURFACE_ID, query=fallback_query),
            reason_code="surface_unknown",
            reason_message=f"Surface is not approved: {requested_surface_id}",
        )

    reducer_owned = requires_shell_state_machine(surface_entry.surface_id)
    shell_state: PortalShellState | None
    if reducer_owned:
        shell_state = reduce_portal_shell_state(
            active_surface_id=surface_entry.surface_id,
            portal_scope=normalized_request.portal_scope,
            current_state=normalized_request.shell_state,
            transition=normalized_request.transition,
            seed_anchor_file=normalized_request.shell_state is None,
        )
        canonical_query = canonical_query_for_shell_state(shell_state, surface_id=surface_entry.surface_id)
    else:
        shell_state = normalized_request.shell_state if isinstance(normalized_request.shell_state, PortalShellState) else None
        canonical_query = canonical_query_for_surface_query(
            normalized_request.surface_query,
            surface_id=surface_entry.surface_id,
        )
    canonical_route = canonical_route_for_surface(surface_entry.surface_id)
    return PortalShellResolution(
        requested_surface_id=requested_surface_id,
        active_surface_id=surface_entry.surface_id,
        selection_status="available",
        allowed=True,
        reducer_owned=reducer_owned,
        shell_state=shell_state,
        canonical_route=canonical_route,
        canonical_query=canonical_query,
        canonical_url=build_canonical_url(surface_id=surface_entry.surface_id, query=canonical_query),
    )


def build_portal_activity_dispatch_bodies(
    *,
    portal_scope: PortalScope | dict[str, Any],
    shell_state: PortalShellState | dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    scope = portal_scope if isinstance(portal_scope, PortalScope) else PortalScope.from_value(portal_scope)
    bodies: dict[str, dict[str, Any]] = {}
    for entry in build_portal_surface_catalog():
        if not requires_shell_state_machine(entry.surface_id):
            continue
        bodies[entry.surface_id] = build_portal_shell_request_payload(
            requested_surface_id=entry.surface_id,
            portal_scope=scope,
            shell_state=shell_state,
            transition={"kind": TRANSITION_ENTER_SURFACE, "surface_id": entry.surface_id},
        )
    return bodies


def activity_icon_id_for_surface(surface_id: object) -> str:
    normalized_surface_id = _as_text(surface_id)
    if normalized_surface_id == SYSTEM_ROOT_SURFACE_ID:
        return "system"
    if normalized_surface_id == NETWORK_ROOT_SURFACE_ID:
        return "network"
    if normalized_surface_id in {UTILITIES_ROOT_SURFACE_ID, UTILITIES_TOOL_EXPOSURE_SURFACE_ID, UTILITIES_INTEGRATIONS_SURFACE_ID}:
        return "utilities"
    if normalized_surface_id in {
        AWS_CSM_TOOL_SURFACE_ID,
    }:
        return "aws"
    if normalized_surface_id == CTS_GIS_TOOL_SURFACE_ID:
        return "cts_gis"
    if normalized_surface_id == FND_DCM_TOOL_SURFACE_ID:
        return "fnd_dcm"
    if normalized_surface_id == FND_EBI_TOOL_SURFACE_ID:
        return "fnd_ebi"
    if normalized_surface_id == WORKBENCH_UI_TOOL_SURFACE_ID:
        return "workbench_ui"
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
    if is_tool_surface(active_surface_id):
        entry = resolve_portal_tool_registry_entry(surface_id=active_surface_id)
        if entry is not None:
            return entry.surface_posture
    return SURFACE_POSTURE_WORKBENCH_PRIMARY


def default_workbench_visible_for_surface(active_surface_id: str) -> bool:
    if is_tool_surface(active_surface_id):
        entry = resolve_portal_tool_registry_entry(surface_id=active_surface_id)
        if entry is not None:
            return entry.default_workbench_visible
        return False
    return True


def foreground_region_for_surface(
    active_surface_id: str,
    *,
    shell_state: PortalShellState | dict[str, Any] | None = None,
    workbench_visible: bool = True,
) -> str:
    if is_tool_surface(active_surface_id):
        if surface_posture_for_surface(active_surface_id) == SURFACE_POSTURE_WORKBENCH_PRIMARY and workbench_visible:
            return "center-workbench"
        return "interface-panel"
    if active_surface_id == SYSTEM_ROOT_SURFACE_ID and isinstance(shell_state, (PortalShellState, dict)):
        state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
        if state.verb == VERB_MEDIATE and state.chrome.interface_panel_open:
            return "interface-panel"
    if not workbench_visible:
        return "interface-panel"
    return "center-workbench"


def apply_surface_posture_to_composition(composition: dict[str, Any]) -> None:
    if not isinstance(composition, dict):
        return
    active_surface_id = _as_text(composition.get("active_surface_id"))
    regions = composition.get("regions")
    if not isinstance(regions, dict):
        return
    workbench = regions.get("workbench")
    inspector = regions.get("inspector")
    if not isinstance(workbench, dict) or not isinstance(inspector, dict):
        return
    workbench_visible = workbench.get("visible", True) is not False
    shell_state = composition.get("shell_state") if isinstance(composition.get("shell_state"), dict) else None
    composition["foreground_shell_region"] = foreground_region_for_surface(
        active_surface_id,
        shell_state=shell_state,
        workbench_visible=workbench_visible,
    )


def _region_visible(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    return value is not False


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
    shell_state: PortalShellState | dict[str, Any] | None = None,
    control_panel_collapsed: bool = False,
) -> dict[str, Any]:
    state = shell_state if isinstance(shell_state, PortalShellState) else (
        PortalShellState.from_value(shell_state) if isinstance(shell_state, dict) else None
    )
    tool_surface = is_tool_surface(active_surface_id)
    surface_posture = surface_posture_for_surface(active_surface_id)
    workbench_region = dict(workbench or {})
    workbench_region.setdefault("schema", PORTAL_SHELL_REGION_WORKBENCH_SCHEMA)
    inspector_region = dict(inspector or {})
    inspector_region.setdefault("schema", PORTAL_SHELL_REGION_INSPECTOR_SCHEMA)
    workbench_visible = _region_visible(
        workbench_region.get("visible"),
        default=default_workbench_visible_for_surface(active_surface_id),
    )
    interface_open = bool(tool_surface)
    if not interface_open and state is not None:
        interface_open = state.chrome.interface_panel_open and state.verb == VERB_MEDIATE
    requested_inspector_visible = inspector_region.get("visible") is True
    if tool_surface:
        if surface_posture == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY:
            workbench_visible = False
            inspector_visible = True
        else:
            workbench_visible = _region_visible(
                workbench_region.get("visible"),
                default=default_workbench_visible_for_surface(active_surface_id),
            )
            inspector_visible = True
    else:
        inspector_visible = bool(interface_open or requested_inspector_visible)
    workbench_region["visible"] = workbench_visible
    inspector_region["visible"] = inspector_visible
    inspector_region["primary_surface"] = bool(
        (interface_open and surface_posture == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY)
        or inspector_region.get("primary_surface") is True
    )
    inspector_region["layout_mode"] = (
        "dominant"
        if interface_open and surface_posture == SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY
        else (_as_text(inspector_region.get("layout_mode")) or "sidebar")
    )
    inspector_collapsed = not inspector_visible
    workbench_collapsed = not bool(workbench_visible)
    workbench_region["collapsed"] = workbench_collapsed
    inspector_region["collapsed"] = inspector_collapsed
    # `inspector` remains the legacy compatibility alias for the public
    # Interface Panel contract during this normalization pass.
    interface_panel_region = dict(inspector_region)
    composition = {
        "schema": PORTAL_SHELL_COMPOSITION_SCHEMA,
        "composition_mode": shell_composition_mode_for_surface(active_surface_id),
        "active_service": map_surface_to_active_service(active_surface_id),
        "active_surface_id": _as_text(active_surface_id),
        "active_tool_surface_id": _as_text(active_surface_id) if is_tool_surface(active_surface_id) else None,
        "foreground_shell_region": foreground_region_for_surface(
            active_surface_id,
            shell_state=state,
            workbench_visible=workbench_visible,
        ),
        "control_panel_collapsed": bool(control_panel_collapsed),
        "inspector_collapsed": inspector_collapsed,
        "interface_panel_collapsed": inspector_collapsed,
        "workbench_collapsed": workbench_collapsed,
        "portal_instance_id": _as_text(portal_instance_id) or PORTAL_SCOPE_DEFAULT_ID,
        "page_title": _as_text(page_title) or "MyCite",
        "page_subtitle": _as_text(page_subtitle),
        "shell_state": None if state is None else state.to_dict(),
        "regions": {
            "activity_bar": {
                "schema": PORTAL_SHELL_REGION_ACTIVITY_BAR_SCHEMA,
                "dispatch": "post_portal_shell",
                "items": list(activity_items),
            },
            "control_panel": dict(control_panel or {}),
            "workbench": workbench_region,
            "inspector": inspector_region,
            "interface_panel": interface_panel_region,
        },
    }
    apply_surface_posture_to_composition(composition)
    return composition


__all__ = [
    "AWS_CSM_TOOL_ENTRYPOINT_ID",
    "AWS_CSM_TOOL_ROUTE",
    "AWS_CSM_TOOL_SURFACE_ID",
    "CTS_GIS_TOOL_ENTRYPOINT_ID",
    "CTS_GIS_TOOL_ROUTE",
    "CTS_GIS_TOOL_SURFACE_ID",
    "FND_DCM_DEFAULT_SITE",
    "FND_DCM_TOOL_ENTRYPOINT_ID",
    "FND_DCM_TOOL_ROUTE",
    "FND_DCM_TOOL_SURFACE_ID",
    "FND_EBI_TOOL_ENTRYPOINT_ID",
    "FND_EBI_TOOL_ROUTE",
    "FND_EBI_TOOL_SURFACE_ID",
    "WORKBENCH_UI_TOOL_ENTRYPOINT_ID",
    "WORKBENCH_UI_TOOL_ROUTE",
    "WORKBENCH_UI_TOOL_SURFACE_ID",
    "FOCUS_LEVEL_DATUM",
    "FOCUS_LEVEL_FILE",
    "FOCUS_LEVEL_OBJECT",
    "FOCUS_LEVEL_SANDBOX",
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
    "PortalFocusSegment",
    "PortalScope",
    "PortalShellChrome",
    "PortalShellRequest",
    "PortalShellResolution",
    "PortalShellState",
    "PortalShellTransition",
    "PortalSurfaceCatalogEntry",
    "PortalToolRegistryEntry",
    "SURFACE_POSTURE_INTERFACE_PANEL_PRIMARY",
    "SURFACE_POSTURE_WORKBENCH_PRIMARY",
    "SYSTEM_ACTIVITY_FILE_KEY",
    "SYSTEM_ANCHOR_FILE_KEY",
    "SYSTEM_PROFILE_BASICS_FILE_KEY",
    "SYSTEM_ROOT_ROUTE",
    "SYSTEM_ROOT_SURFACE_ID",
    "SYSTEM_SURFACE_IDS",
    "SYSTEM_SANDBOX_QUERY_FILE_TOKEN",
    "TOOL_KIND_GENERAL",
    "TOOL_KIND_HOST_ALIAS",
    "TOOL_KIND_SERVICE",
    "TOOL_SURFACE_IDS",
    "TRANSITION_BACK_OUT",
    "TRANSITION_CLOSE_INTERFACE_PANEL",
    "TRANSITION_ENTER_SURFACE",
    "TRANSITION_FOCUS_DATUM",
    "TRANSITION_FOCUS_FILE",
    "TRANSITION_FOCUS_OBJECT",
    "TRANSITION_OPEN_INTERFACE_PANEL",
    "TRANSITION_SET_VERB",
    "UTILITIES_INTEGRATIONS_ROUTE",
    "UTILITIES_INTEGRATIONS_SURFACE_ID",
    "UTILITIES_ROOT_ROUTE",
    "UTILITIES_ROOT_SURFACE_ID",
    "UTILITIES_TOOL_EXPOSURE_ROUTE",
    "UTILITIES_TOOL_EXPOSURE_SURFACE_ID",
    "VERB_INVESTIGATE",
    "VERB_MANIPULATE",
    "VERB_MEDIATE",
    "VERB_NAVIGATE",
    "activity_icon_id_for_surface",
    "apply_surface_posture_to_composition",
    "build_canonical_url",
    "build_portal_activity_dispatch_bodies",
    "build_portal_shell_request_payload",
    "build_portal_shell_state_from_query",
    "build_portal_surface_catalog",
    "build_portal_tool_registry_entries",
    "build_shell_composition_payload",
    "canonical_query_for_surface_query",
    "canonical_query_for_shell_state",
    "canonical_route_for_surface",
    "canonicalize_portal_shell_state",
    "default_focus_path",
    "default_workbench_visible_for_surface",
    "focus_level_for_shell_state",
    "foreground_region_for_surface",
    "initial_portal_shell_state",
    "is_tool_surface",
    "map_surface_to_active_service",
    "reduce_portal_shell_state",
    "requires_shell_state_machine",
    "resolve_portal_shell_request",
    "resolve_portal_surface",
    "resolve_portal_tool_registry_entry",
    "segment_id_for_level",
    "shell_composition_mode_for_surface",
    "surface_posture_for_surface",
    "surface_root_id",
]
