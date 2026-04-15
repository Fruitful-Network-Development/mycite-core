from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from MyCiteV2.packages.state_machine.portal_shell import (
    AWS_CSM_TOOL_ENTRYPOINT_ID,
    AWS_CSM_TOOL_ROUTE,
    AWS_CSM_TOOL_SURFACE_ID,
    CTS_GIS_TOOL_ENTRYPOINT_ID,
    CTS_GIS_TOOL_ROUTE,
    CTS_GIS_TOOL_SURFACE_ID,
    FND_EBI_TOOL_ENTRYPOINT_ID,
    FND_EBI_TOOL_ROUTE,
    FND_EBI_TOOL_SURFACE_ID,
    NETWORK_ROOT_ROUTE,
    NETWORK_ROOT_SURFACE_ID,
    PORTAL_SCOPE_DEFAULT_ID,
    PORTAL_SHELL_ENTRYPOINT_ID,
    PORTAL_SHELL_REQUEST_SCHEMA,
    PORTAL_SHELL_STATE_SCHEMA,
    SYSTEM_ROOT_ROUTE,
    SYSTEM_ROOT_SURFACE_ID,
    UTILITIES_INTEGRATIONS_ROUTE,
    UTILITIES_INTEGRATIONS_SURFACE_ID,
    UTILITIES_ROOT_ROUTE,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_ROUTE,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    build_portal_tool_registry_entries,
)

PORTAL_RUNTIME_ENVELOPE_SCHEMA = "mycite.v2.portal.runtime.envelope.v1"
PORTAL_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA = "mycite.v2.portal.runtime_entrypoint_descriptor.v1"

SYSTEM_ROOT_SURFACE_SCHEMA = "mycite.v2.portal.system.workspace.surface.v1"
NETWORK_ROOT_SURFACE_SCHEMA = "mycite.v2.portal.network.surface.v1"
UTILITIES_ROOT_SURFACE_SCHEMA = "mycite.v2.portal.utilities.surface.v1"
UTILITIES_TOOL_EXPOSURE_SURFACE_SCHEMA = "mycite.v2.portal.utilities.tool_exposure.surface.v1"
UTILITIES_INTEGRATIONS_SURFACE_SCHEMA = "mycite.v2.portal.utilities.integrations.surface.v1"
AWS_CSM_TOOL_SURFACE_SCHEMA = "mycite.v2.portal.system.tools.aws_csm.surface.v1"
CTS_GIS_TOOL_SURFACE_SCHEMA = "mycite.v2.portal.system.tools.cts_gis.surface.v1"
FND_EBI_TOOL_SURFACE_SCHEMA = "mycite.v2.portal.system.tools.fnd_ebi.surface.v1"

AWS_CSM_TOOL_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.aws_csm.request.v1"
CTS_GIS_TOOL_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.cts_gis.request.v1"
FND_EBI_TOOL_REQUEST_SCHEMA = "mycite.v2.portal.system.tools.fnd_ebi.request.v1"
SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA = "mycite.v2.portal.system.workspace.profile_basics.action.request.v1"

PORTAL_RUNTIME_REQUIRED_ENVELOPE_KEYS = (
    "schema",
    "portal_scope",
    "requested_surface_id",
    "surface_id",
    "entrypoint_id",
    "read_write_posture",
    "reducer_owned",
    "canonical_route",
    "canonical_query",
    "canonical_url",
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


def _canonical_tool_id(raw_tool_id: object, *, known_tool_ids: set[str]) -> str:
    tool_id = _as_text(raw_tool_id)
    if not tool_id:
        return ""
    if tool_id in known_tool_ids:
        return tool_id
    return tool_id


def _bool_or_default(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _normalize_required_configuration(value: object) -> tuple[str, ...]:
    if value in {None, ""}:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError("runtime_entrypoint.required_configuration must be a list, tuple, or null")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        key = _as_text(item)
        if not key or key in seen:
            continue
        normalized.append(key)
        seen.add(key)
    return tuple(normalized)


def build_allow_all_tool_exposure_policy(
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
        "enabled_tools": {tool_id: True for tool_id in normalized_known},
        "policy_source": "runtime_default_allow_all",
    }


def build_tool_exposure_policy(
    raw_policy: object,
    *,
    known_tool_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    normalized_known = _normalize_known_tool_ids(known_tool_ids)
    known_set = set(normalized_known)
    configured_tools: dict[str, bool] = {}
    enabled_tools: dict[str, bool] = {}
    unknown_tool_ids: list[str] = []
    invalid_tool_ids: list[str] = []

    if not isinstance(raw_policy, dict):
        raw_policy = {}

    for raw_tool_id, raw_entry in raw_policy.items():
        tool_id = _canonical_tool_id(raw_tool_id, known_tool_ids=known_set)
        if not tool_id:
            continue
        if tool_id not in known_set:
            unknown_tool_ids.append(tool_id)
            continue
        if isinstance(raw_entry, bool):
            configured_tools[tool_id] = configured_tools.get(tool_id, False) or True
            enabled_tools[tool_id] = enabled_tools.get(tool_id, False) or raw_entry
            continue
        if not isinstance(raw_entry, dict):
            invalid_tool_ids.append(tool_id)
            continue
        configured_value = raw_entry.get("configured")
        enabled_value = raw_entry.get("enabled")
        next_configured = _bool_or_default(configured_value, default=True)
        next_enabled = _bool_or_default(enabled_value, default=next_configured)
        configured_tools[tool_id] = configured_tools.get(tool_id, False) or next_configured
        enabled_tools[tool_id] = enabled_tools.get(tool_id, False) or next_enabled

    configured_tool_ids = [tool_id for tool_id in normalized_known if configured_tools.get(tool_id) is True]
    enabled_tool_ids = [tool_id for tool_id in normalized_known if enabled_tools.get(tool_id) is True]
    disabled_tool_ids = [tool_id for tool_id in normalized_known if enabled_tools.get(tool_id) is False]
    missing_tool_ids = [
        tool_id for tool_id in normalized_known if tool_id not in configured_tools and tool_id not in enabled_tools
    ]

    return {
        "known_tool_ids": list(normalized_known),
        "configured_tool_ids": list(configured_tool_ids),
        "enabled_tool_ids": list(enabled_tool_ids),
        "disabled_tool_ids": list(disabled_tool_ids),
        "missing_tool_ids": list(missing_tool_ids),
        "unknown_tool_ids": list(unknown_tool_ids),
        "invalid_tool_ids": list(invalid_tool_ids),
        "configured_tools": dict(configured_tools),
        "enabled_tools": dict(enabled_tools),
        "policy_source": "private_config_json",
    }


def tool_exposure_configured(tool_exposure_policy: dict[str, Any] | None, *, tool_id: str) -> bool:
    if tool_exposure_policy is None:
        return True
    configured_tools = tool_exposure_policy.get("configured_tools")
    if not isinstance(configured_tools, dict):
        return False
    return configured_tools.get(_as_text(tool_id), False) is True


def tool_exposure_enabled(tool_exposure_policy: dict[str, Any] | None, *, tool_id: str) -> bool:
    if tool_exposure_policy is None:
        return True
    enabled_tools = tool_exposure_policy.get("enabled_tools")
    if not isinstance(enabled_tools, dict):
        return False
    return enabled_tools.get(_as_text(tool_id), False) is True


@dataclass(frozen=True)
class PortalRuntimeEntrypointDescriptor:
    entrypoint_id: str
    callable_path: str
    surface_id: str
    route: str
    request_schema: str
    surface_schema: str
    read_write_posture: str
    required_configuration: tuple[str, ...] = ()
    schema: str = field(default=PORTAL_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if not _as_text(self.entrypoint_id):
            raise ValueError("runtime_entrypoint.entrypoint_id is required")
        if not _as_text(self.callable_path):
            raise ValueError("runtime_entrypoint.callable_path is required")
        if not _as_text(self.surface_id):
            raise ValueError("runtime_entrypoint.surface_id is required")
        if not _as_text(self.route):
            raise ValueError("runtime_entrypoint.route is required")
        if not _as_text(self.request_schema):
            raise ValueError("runtime_entrypoint.request_schema is required")
        if not _as_text(self.surface_schema):
            raise ValueError("runtime_entrypoint.surface_schema is required")
        if self.read_write_posture not in {"read-only", "write"}:
            raise ValueError("runtime_entrypoint.read_write_posture must be read-only or write")
        object.__setattr__(
            self,
            "required_configuration",
            _normalize_required_configuration(self.required_configuration),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "entrypoint_id": self.entrypoint_id,
            "callable_path": self.callable_path,
            "surface_id": self.surface_id,
            "route": self.route,
            "request_schema": self.request_schema,
            "surface_schema": self.surface_schema,
            "read_write_posture": self.read_write_posture,
            "required_configuration": list(self.required_configuration),
        }


def build_portal_runtime_entrypoint_catalog() -> tuple[PortalRuntimeEntrypointDescriptor, ...]:
    return (
        PortalRuntimeEntrypointDescriptor(
            entrypoint_id=PORTAL_SHELL_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.portal_shell_runtime.run_portal_shell_entry",
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            route="/portal/api/v2/shell",
            request_schema=PORTAL_SHELL_REQUEST_SCHEMA,
            surface_schema=SYSTEM_ROOT_SURFACE_SCHEMA,
            read_write_posture="read-only",
        ),
        PortalRuntimeEntrypointDescriptor(
            entrypoint_id=AWS_CSM_TOOL_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.portal_aws_runtime.run_portal_aws_csm",
            surface_id=AWS_CSM_TOOL_SURFACE_ID,
            route="/portal/api/v2/system/tools/aws-csm",
            request_schema=AWS_CSM_TOOL_REQUEST_SCHEMA,
            surface_schema=AWS_CSM_TOOL_SURFACE_SCHEMA,
            read_write_posture="read-only",
            required_configuration=(),
        ),
        PortalRuntimeEntrypointDescriptor(
            entrypoint_id=CTS_GIS_TOOL_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime.run_portal_cts_gis",
            surface_id=CTS_GIS_TOOL_SURFACE_ID,
            route="/portal/api/v2/system/tools/cts-gis",
            request_schema=CTS_GIS_TOOL_REQUEST_SCHEMA,
            surface_schema=CTS_GIS_TOOL_SURFACE_SCHEMA,
            read_write_posture="read-only",
            required_configuration=("data_dir",),
        ),
        PortalRuntimeEntrypointDescriptor(
            entrypoint_id=FND_EBI_TOOL_ENTRYPOINT_ID,
            callable_path="MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime.run_portal_fnd_ebi",
            surface_id=FND_EBI_TOOL_SURFACE_ID,
            route="/portal/api/v2/system/tools/fnd-ebi",
            request_schema=FND_EBI_TOOL_REQUEST_SCHEMA,
            surface_schema=FND_EBI_TOOL_SURFACE_SCHEMA,
            read_write_posture="read-only",
            required_configuration=("webapps_root",),
        ),
    )


def resolve_portal_runtime_entrypoint(entrypoint_id: object) -> PortalRuntimeEntrypointDescriptor | None:
    normalized_entrypoint_id = _as_text(entrypoint_id)
    for descriptor in build_portal_runtime_entrypoint_catalog():
        if descriptor.entrypoint_id == normalized_entrypoint_id:
            return descriptor
    return None


def surface_schema_for_surface(surface_id: str) -> str:
    mapping = {
        SYSTEM_ROOT_SURFACE_ID: SYSTEM_ROOT_SURFACE_SCHEMA,
        NETWORK_ROOT_SURFACE_ID: NETWORK_ROOT_SURFACE_SCHEMA,
        UTILITIES_ROOT_SURFACE_ID: UTILITIES_ROOT_SURFACE_SCHEMA,
        UTILITIES_TOOL_EXPOSURE_SURFACE_ID: UTILITIES_TOOL_EXPOSURE_SURFACE_SCHEMA,
        UTILITIES_INTEGRATIONS_SURFACE_ID: UTILITIES_INTEGRATIONS_SURFACE_SCHEMA,
        AWS_CSM_TOOL_SURFACE_ID: AWS_CSM_TOOL_SURFACE_SCHEMA,
        CTS_GIS_TOOL_SURFACE_ID: CTS_GIS_TOOL_SURFACE_SCHEMA,
        FND_EBI_TOOL_SURFACE_ID: FND_EBI_TOOL_SURFACE_SCHEMA,
    }
    return mapping.get(_as_text(surface_id), SYSTEM_ROOT_SURFACE_SCHEMA)


def route_for_surface(surface_id: str) -> str:
    mapping = {
        SYSTEM_ROOT_SURFACE_ID: SYSTEM_ROOT_ROUTE,
        NETWORK_ROOT_SURFACE_ID: NETWORK_ROOT_ROUTE,
        UTILITIES_ROOT_SURFACE_ID: UTILITIES_ROOT_ROUTE,
        UTILITIES_TOOL_EXPOSURE_SURFACE_ID: UTILITIES_TOOL_EXPOSURE_ROUTE,
        UTILITIES_INTEGRATIONS_SURFACE_ID: UTILITIES_INTEGRATIONS_ROUTE,
        AWS_CSM_TOOL_SURFACE_ID: AWS_CSM_TOOL_ROUTE,
        CTS_GIS_TOOL_SURFACE_ID: CTS_GIS_TOOL_ROUTE,
        FND_EBI_TOOL_SURFACE_ID: FND_EBI_TOOL_ROUTE,
    }
    return mapping.get(_as_text(surface_id), SYSTEM_ROOT_ROUTE)


def build_portal_runtime_error(*, code: str, message: str) -> dict[str, str]:
    return {
        "code": _as_text(code) or "runtime_error",
        "message": _as_text(message) or "The portal runtime could not complete the request.",
    }


def build_portal_runtime_envelope(
    *,
    portal_scope: dict[str, Any] | None,
    requested_surface_id: str,
    surface_id: str,
    entrypoint_id: str,
    read_write_posture: str,
    reducer_owned: bool,
    canonical_route: str,
    canonical_query: dict[str, Any] | None,
    canonical_url: str,
    shell_state: dict[str, Any] | None,
    surface_payload: dict[str, Any] | None,
    shell_composition: dict[str, Any] | None,
    warnings: list[dict[str, Any]] | list[str] | None,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": PORTAL_RUNTIME_ENVELOPE_SCHEMA,
        "portal_scope": dict(portal_scope or {"scope_id": PORTAL_SCOPE_DEFAULT_ID, "capabilities": []}),
        "requested_surface_id": _as_text(requested_surface_id) or SYSTEM_ROOT_SURFACE_ID,
        "surface_id": _as_text(surface_id) or SYSTEM_ROOT_SURFACE_ID,
        "entrypoint_id": _as_text(entrypoint_id) or PORTAL_SHELL_ENTRYPOINT_ID,
        "read_write_posture": _as_text(read_write_posture) or "read-only",
        "reducer_owned": bool(reducer_owned),
        "canonical_route": _as_text(canonical_route) or route_for_surface(surface_id),
        "canonical_query": dict(canonical_query or {}),
        "canonical_url": _as_text(canonical_url) or route_for_surface(surface_id),
        "shell_state": dict(shell_state or {"schema": PORTAL_SHELL_STATE_SCHEMA}),
        "surface_payload": dict(surface_payload or {"schema": surface_schema_for_surface(surface_id)}),
        "shell_composition": dict(shell_composition or {}),
        "warnings": list(warnings or []),
        "error": dict(error) if isinstance(error, dict) else None,
    }


def build_runtime_catalog_public_summary() -> list[dict[str, Any]]:
    tool_ids = [entry.tool_id for entry in build_portal_tool_registry_entries()]
    summary: list[dict[str, Any]] = []
    for descriptor in build_portal_runtime_entrypoint_catalog():
        row = descriptor.to_dict()
        row["known_tools"] = list(tool_ids)
        summary.append(row)
    return summary


__all__ = [
    "AWS_CSM_TOOL_REQUEST_SCHEMA",
    "AWS_CSM_TOOL_SURFACE_SCHEMA",
    "CTS_GIS_TOOL_REQUEST_SCHEMA",
    "CTS_GIS_TOOL_SURFACE_SCHEMA",
    "FND_EBI_TOOL_REQUEST_SCHEMA",
    "FND_EBI_TOOL_SURFACE_SCHEMA",
    "NETWORK_ROOT_SURFACE_SCHEMA",
    "PORTAL_RUNTIME_ENVELOPE_SCHEMA",
    "PORTAL_RUNTIME_ENTRYPOINT_DESCRIPTOR_SCHEMA",
    "PORTAL_RUNTIME_REQUIRED_ENVELOPE_KEYS",
    "SYSTEM_ROOT_SURFACE_SCHEMA",
    "SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA",
    "UTILITIES_INTEGRATIONS_SURFACE_SCHEMA",
    "UTILITIES_ROOT_SURFACE_SCHEMA",
    "UTILITIES_TOOL_EXPOSURE_SURFACE_SCHEMA",
    "PortalRuntimeEntrypointDescriptor",
    "build_allow_all_tool_exposure_policy",
    "build_portal_runtime_envelope",
    "build_portal_runtime_entrypoint_catalog",
    "build_portal_runtime_error",
    "build_runtime_catalog_public_summary",
    "build_tool_exposure_policy",
    "resolve_portal_runtime_entrypoint",
    "route_for_surface",
    "surface_schema_for_surface",
    "tool_exposure_configured",
    "tool_exposure_enabled",
]
