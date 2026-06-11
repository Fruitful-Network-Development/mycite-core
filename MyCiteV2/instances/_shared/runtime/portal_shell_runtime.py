from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import (
    _invalidate_workbench_projection_cache,
    build_system_workspace_bundle,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    PORTAL_RUNTIME_ENVELOPE_SCHEMA,
    SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA,
    attach_region_family_contract,
    build_allow_all_tool_exposure_policy,
    build_portal_runtime_envelope,
    build_portal_runtime_error,
    surface_schema_for_surface,
)
from MyCiteV2.packages.adapters.sql import (
    SqliteAuditLogAdapter,
    SqlitePortalAuthorityAdapter,
    SqliteSystemDatumStoreAdapter,
)
from MyCiteV2.packages.ports.portal_authority import PortalAuthorityRequest
from MyCiteV2.packages.state_machine.portal_shell import (
    AGRO_ERP_TOOL_SURFACE_ID,
    NETWORK_ROOT_SURFACE_ID,
    PORTAL_SHELL_ENTRYPOINT_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    SYSTEM_PROFILE_BASICS_FILE_KEY,
    SYSTEM_ROOT_ROUTE,
    SYSTEM_ROOT_SURFACE_ID,
    SYSTEM_SURFACE_IDS,
    TRANSITION_FOCUS_FILE,
    UTILITIES_EXTENSIONS_SURFACE_ID,
    UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
    UTILITIES_PERIPHERALS_SURFACE_ID,
    UTILITIES_ROOT_SURFACE_ID,
    UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
    UTILITIES_TOOLS_SURFACE_ID,
    WORKBENCH_UI_TOOL_SURFACE_ID,
    PortalScope,
    PortalShellRequest,
    PortalShellState,
    activity_icon_id_for_surface,
    build_canonical_url,
    build_portal_shell_request_payload,
    build_portal_surface_catalog,
    build_portal_tool_registry_entries,
    build_shell_composition_payload,
    canonical_query_for_shell_state,
    canonicalize_portal_shell_state,
    initial_portal_shell_state,
    resolve_portal_shell_request,
)

_log = logging.getLogger("mycite.portal_host")


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _path_or_none(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    return Path(path)


def _normalize_authority_mode(value: object) -> str:
    del value
    return "sql_primary"


def _portal_authority_source(
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None,
) -> Any | None:
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return None
    known_tool_ids = tuple(entry.tool_id for entry in build_portal_tool_registry_entries())
    result = SqlitePortalAuthorityAdapter(authority_path).read_portal_authority(
        PortalAuthorityRequest(scope_id=portal_instance_id, known_tool_ids=known_tool_ids)
    )
    return result.source


def _portal_scope_from_request(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> PortalScope:
    del authority_mode, tool_exposure_policy
    normalized_payload = request_payload if isinstance(request_payload, dict) else {}
    if isinstance(normalized_payload.get("portal_scope"), dict):
        raw_scope = dict(normalized_payload.get("portal_scope") or {})
        raw_scope.setdefault("scope_id", portal_instance_id)
        existing_capabilities = raw_scope.get("capabilities")
        if not isinstance(existing_capabilities, list) or not existing_capabilities:
            authority_source = _portal_authority_source(
                portal_instance_id=portal_instance_id,
                authority_db_file=authority_db_file,
            )
            raw_scope["capabilities"] = list(authority_source.capabilities) if authority_source is not None else []
        return PortalScope.from_value(raw_scope)
    authority_source = _portal_authority_source(
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
    )
    if authority_source is not None:
        return PortalScope(
            scope_id=authority_source.scope_id,
            capabilities=authority_source.capabilities,
        )
    return PortalScope(scope_id=portal_instance_id, capabilities=())


def _normalize_request(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
    tool_exposure_policy: dict[str, Any] | None = None,
) -> PortalShellRequest:
    portal_scope = _portal_scope_from_request(
        request_payload,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
        tool_exposure_policy=tool_exposure_policy,
    )
    normalized_payload = dict(request_payload or {})
    normalized_payload["portal_scope"] = portal_scope.to_dict()
    if "schema" not in normalized_payload:
        normalized_payload["schema"] = "mycite.v2.portal.shell.request.v1"
    return PortalShellRequest.from_dict(normalized_payload)


def _resolved_tool_exposure_policy(
    tool_exposure_policy: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    del authority_mode
    authority_source = _portal_authority_source(
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
    )
    if authority_source is not None and isinstance(authority_source.tool_exposure_policy, dict):
        return dict(authority_source.tool_exposure_policy)
    if tool_exposure_policy is not None:
        return tool_exposure_policy
    return build_allow_all_tool_exposure_policy(known_tool_ids=[entry.tool_id for entry in build_portal_tool_registry_entries()])


def _sql_runtime_error_for_surface(
    *,
    surface_id: str,
    portal_instance_id: str,
    authority_db_file: str | Path | None,
) -> dict[str, str] | None:
    if surface_id not in SYSTEM_SURFACE_IDS:
        return None
    authority_path = _path_or_none(authority_db_file)
    if authority_path is None:
        return build_portal_runtime_error(
            code="sql_authority_required",
            message="The MOS SQL authority database is required for SYSTEM surfaces.",
        )
    authority_source = _portal_authority_source(
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_path,
    )
    if authority_source is None:
        return build_portal_runtime_error(
            code="sql_portal_authority_missing",
            message="The MOS SQL authority database is missing the portal authority snapshot for this scope.",
        )
    if surface_id in {SYSTEM_ROOT_SURFACE_ID, WORKBENCH_UI_TOOL_SURFACE_ID, AGRO_ERP_TOOL_SURFACE_ID}:
        datum_store = SqliteSystemDatumStoreAdapter(authority_path)
        if not datum_store.has_authoritative_catalog(portal_instance_id) or not datum_store.has_system_workbench(portal_instance_id):
            return build_portal_runtime_error(
                code="sql_authority_uninitialized",
                message="The MOS SQL authority database is not initialized for the requested tenant.",
            )
    return None


def _integration_flags(
    *,
    data_dir: str | Path | None,
    webapps_root: str | Path | None,
) -> dict[str, bool]:
    return {
        "data_dir": bool(data_dir and Path(data_dir).exists()),
        "webapps_root": bool(webapps_root and Path(webapps_root).exists()),
    }


def _tool_posture_rows(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    integration_flags: dict[str, bool],
    portal_instance_id: str,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> list[dict[str, Any]]:
    policy = _resolved_tool_exposure_policy(
        tool_exposure_policy,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    rows: list[dict[str, Any]] = []
    for entry in build_portal_tool_registry_entries():
        configured_tools = policy.get("configured_tools") if isinstance(policy.get("configured_tools"), dict) else {}
        enabled_tools = policy.get("enabled_tools") if isinstance(policy.get("enabled_tools"), dict) else {}
        configured = (
            configured_tools.get(entry.tool_id, entry.default_enabled) is True
            if isinstance(configured_tools, dict)
            else entry.default_enabled
        )
        enabled = (
            enabled_tools.get(entry.tool_id, entry.default_enabled) is True
            if isinstance(enabled_tools, dict)
            else entry.default_enabled
        )
        integration_name = {}.get(entry.tool_id, "")
        missing_integrations = []
        if integration_name and not integration_flags.get(integration_name, False):
            missing_integrations.append(integration_name)
        missing_capabilities = [
            capability for capability in entry.required_capabilities if capability not in portal_scope.capabilities
        ]
        rows.append(
            {
                "tool_id": entry.tool_id,
                "label": entry.label,
                "route": entry.route,
                "surface_id": entry.surface_id,
                "is_extension": bool(getattr(entry, "is_extension", False)),
                "configured": configured,
                "enabled": enabled,
                "operational": bool(configured and enabled and not missing_integrations and not missing_capabilities),
                "missing_integrations": missing_integrations,
                "required_capabilities": list(entry.required_capabilities),
                "missing_capabilities": missing_capabilities,
                "summary": entry.summary,
            }
        )
    return rows


def _activity_items(
    *,
    portal_scope: PortalScope,
    active_surface_id: str,
    shell_state: PortalShellState | None,
) -> list[dict[str, Any]]:
    # Plan v2: only Network + Utilities live in the activity-nav list.
    # The portal logo at the top of the activity bar (portal.html) is
    # the System entry — making "three slots: logo + network + utilities"
    # the canonical chrome. Tools (CTS-GIS map, etc.) are invoked from
    # the menubar search and paint into the workbench's visualization
    # panel rather than owning their own activity-bar slot.
    # Phase A: these roots are query-native, so navigation is direct-href
    # (no reducer dispatch bodies).
    del shell_state
    visible_surface_ids = [
        NETWORK_ROOT_SURFACE_ID,
        UTILITIES_ROOT_SURFACE_ID,
    ]
    items: list[dict[str, Any]] = []
    for entry in build_portal_surface_catalog():
        if entry.surface_id not in visible_surface_ids:
            continue
        items.append(
            {
                "item_id": entry.surface_id,
                "label": entry.label,
                "icon_id": activity_icon_id_for_surface(entry.surface_id),
                "href": entry.route,
                "active": entry.surface_id == active_surface_id,
                "nav_kind": "surface",
                "nav_behavior": "direct",
            }
        )
    return items


def _plain_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    active_surface_id: str,
    title: str,
    surface_group_title: str,
    surface_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    # Phase A: roots are query-native — navigate by direct href, no reducer
    # dispatch bodies.
    del shell_state
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "plain_navigation",
        "title": title,
        "sections": [
            {
                "title": "Roots",
                "entries": [
                    {
                        "label": "System",
                        "href": "/portal/system",
                        "active": active_surface_id == SYSTEM_ROOT_SURFACE_ID,
                    },
                    {
                        "label": "Network",
                        "href": "/portal/network",
                        "active": active_surface_id == NETWORK_ROOT_SURFACE_ID,
                    },
                    {
                        "label": "Utilities",
                        "href": "/portal/utilities",
                        "active": active_surface_id == UTILITIES_ROOT_SURFACE_ID,
                    },
                ],
            },
            {
                "title": surface_group_title,
                "entries": surface_entries,
            },
        ],
    }


def _utilities_surface_label(surface_id: str) -> str:
    if surface_id == UTILITIES_EXTENSIONS_SURFACE_ID:
        return "Extensions"
    if surface_id == UTILITIES_GRANTEE_PROFILE_SURFACE_ID:
        return "Grantee Profile"
    if surface_id == UTILITIES_TOOLS_SURFACE_ID:
        return "Tools"
    if surface_id == UTILITIES_PERIPHERALS_SURFACE_ID:
        return "Peripherals"
    if surface_id == UTILITIES_TOOL_EXPOSURE_SURFACE_ID:
        return "Tool Exposure (legacy)"
    return "Overview"


def _utilities_control_panel(
    *,
    active_surface_id: str,
) -> dict[str, Any]:
    # Phase 14b: control-panel navigation lists the 4 new dedicated
    # surfaces. The legacy "Tool Exposure" + "Integrations" routes still
    # work but 302-redirect; their entries are removed from the
    # operator-facing nav.
    entries = [
        {
            "label": "Extensions",
            "href": "/portal/utilities/extensions",
            "active": active_surface_id == UTILITIES_EXTENSIONS_SURFACE_ID,
        },
        {
            "label": "Grantee Profile",
            "href": "/portal/utilities/grantee-profile",
            "active": active_surface_id == UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
        },
        {
            "label": "Tools",
            "href": "/portal/utilities/tools",
            "active": active_surface_id == UTILITIES_TOOLS_SURFACE_ID,
        },
        {
            "label": "Peripherals",
            "href": "/portal/utilities/peripherals",
            "active": active_surface_id == UTILITIES_PERIPHERALS_SURFACE_ID,
        },
    ]
    if active_surface_id == UTILITIES_ROOT_SURFACE_ID:
        for entry in entries:
            entry["active"] = False
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "UTILITIES",
        "context_items": [
            {"label": "Root", "value": "UTILITIES"},
            {"label": "Section", "value": _utilities_surface_label(active_surface_id)},
        ],
        "verb_tabs": [],
        "groups": [
            {
                "title": "Sections",
                "entries": entries,
            }
        ],
        "actions": [],
    }


def _metric_card(label: str, value: object, *, meta: object = "") -> dict[str, str]:
    return {
        "label": _as_text(label),
        "value": _as_text(value) or "—",
        "meta": _as_text(meta),
    }


def _rows_for_tool_table(tool_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in tool_rows:
        rows.append(
            {
                "tool": row["label"],
                "configured": "yes" if row["configured"] else "no",
                "enabled": "yes" if row["enabled"] else "no",
                "operational": "yes" if row["operational"] else "no",
            }
        )
    return rows


def _surface_payload_for_network(
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
    surface_query: dict[str, str] | None,
) -> dict[str, Any]:
    from MyCiteV2.packages.adapters.filesystem import FilesystemNetworkRootReadModelAdapter
    from MyCiteV2.packages.modules.cross_domain.network_root import NetworkRootReadModelService

    service = NetworkRootReadModelService(
        FilesystemNetworkRootReadModelAdapter(
            data_dir=data_dir,
            private_dir=private_dir,
            local_audit_file=audit_storage_file,
        )
    )
    projection = service.read_surface(
        portal_tenant_id=portal_instance_id,
        portal_domain=portal_domain,
        surface_query=surface_query,
    )
    projection["schema"] = surface_schema_for_surface(NETWORK_ROOT_SURFACE_ID)
    return projection


def _network_entry(
    *,
    label: str,
    href: str,
    active: bool = False,
    meta: object = "",
    shell_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "label": label,
        "href": href,
        "active": active,
    }
    meta_text = _as_text(meta)
    if meta_text:
        entry["meta"] = meta_text
    if shell_request is not None:
        entry["shell_request"] = shell_request
    return entry


def _network_control_panel(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    active_surface_id: str,
    surface_payload: dict[str, Any],
) -> dict[str, Any]:
    workspace = dict(surface_payload.get("workspace") or {})
    active_filters = dict(workspace.get("active_filters") or {})
    event_type_filters = list(workspace.get("event_type_filters") or [])
    contract_filters = list(workspace.get("contract_filters") or [])
    system_log_request = build_portal_shell_request_payload(
        requested_surface_id=NETWORK_ROOT_SURFACE_ID,
        portal_scope=portal_scope,
        shell_state=shell_state,
        surface_query={"view": "system_logs"},
    )
    event_entries = []
    for row in event_type_filters:
        event_type_id = _as_text(row.get("event_type_id"))
        event_entries.append(
            _network_entry(
                label=_as_text(row.get("label") or event_type_id) or "Event Type",
                href=f"/portal/network?view=system_logs&type={event_type_id}",
                active=bool(row.get("active")),
                meta=f"{int(row.get('count') or 0)} row(s)",
                shell_request=build_portal_shell_request_payload(
                    requested_surface_id=NETWORK_ROOT_SURFACE_ID,
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    surface_query={"view": "system_logs", "type": event_type_id},
                ),
            )
        )
    contract_entries = []
    for row in contract_filters:
        contract_id = _as_text(row.get("contract_id"))
        contract_entries.append(
            _network_entry(
                label=contract_id or "Contract",
                href=f"/portal/network?view=system_logs&contract={contract_id}",
                active=bool(row.get("active")),
                meta=f"{_as_text(row.get('relationship_kind')) or 'contract'} · {int(row.get('count') or 0)} row(s)",
                shell_request=build_portal_shell_request_payload(
                    requested_surface_id=NETWORK_ROOT_SURFACE_ID,
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    surface_query={"view": "system_logs", "contract": contract_id},
                ),
            )
        )
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "NETWORK",
        "context_items": [
            {"label": "Root", "value": "NETWORK"},
            {"label": "View", "value": "system_logs"},
            {"label": "Contract", "value": _as_text(active_filters.get("contract_id")) or "all"},
            {"label": "Type", "value": _as_text(active_filters.get("event_type_id")) or "all"},
        ],
        "verb_tabs": [],
        "groups": [
            {
                "title": "Views",
                "entries": [
                    _network_entry(
                        label="System Logs",
                        href="/portal/network?view=system_logs",
                        active=not _as_text(active_filters.get("contract_id")) and not _as_text(active_filters.get("event_type_id")),
                        meta="canonical workbench",
                        shell_request=system_log_request,
                    )
                ],
            },
            {
                "title": "Contracts",
                "entries": contract_entries,
            },
            {
                "title": "Event Types",
                "entries": event_entries,
            },
        ],
        "actions": [],
    }


def _network_workbench(surface_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "network_system_log_workbench",
        "title": _as_text(surface_payload.get("title")) or "Network",
        "subtitle": _as_text(surface_payload.get("subtitle")),
        "visible": True,
        "surface_payload": surface_payload,
    }


def _surface_payload_for_utilities_root(tool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Phase 14b: navigation links into the four dedicated Utilities surfaces.
    # The old "Tool Exposure" + "Integrations" entries are removed from the
    # cards (their routes 302-redirect to the new equivalents).
    return {
        "schema": surface_schema_for_surface(UTILITIES_ROOT_SURFACE_ID),
        "kind": "utilities_overview",
        "title": "Utilities",
        "subtitle": "Extensions, grantee profile, tools, peripherals.",
        "cards": [
            _metric_card("extensions", 4),
            _metric_card("grantees configured", "managed via Grantee Profile"),
            _metric_card("tools", "1 (CTS-GIS)"),
        ],
        "sections": [
            {
                "title": "Utilities children",
                "rows": [
                    {"label": "Extensions", "status": "available", "detail": "/portal/utilities/extensions"},
                    {"label": "Grantee Profile", "status": "available", "detail": "/portal/utilities/grantee-profile"},
                    {"label": "Tools", "status": "available", "detail": "/portal/utilities/tools"},
                    {"label": "Peripherals", "status": "available", "detail": "/portal/utilities/peripherals"},
                ],
            }
        ],
    }


def _resolve_utilities_mode(query: dict[str, str], *, default_to_global: bool) -> str:
    """Resolve GLOBAL ("Overall") vs per-grantee mode from the surface query.

    Precedence: an explicit ``utilities_mode`` wins; else any non-empty
    ``selected_grantee_msn`` implies grantee mode; else the surface default
    (the Extensions surface defaults to global, the Grantee-Profile surface to
    grantee so its single-grantee editor behavior is preserved exactly).
    """
    mode_q = _as_text(query.get("utilities_mode"))
    if mode_q in {"global", "grantee"}:
        return mode_q
    if _as_text(query.get("selected_grantee_msn")):
        return "grantee"
    return "global" if default_to_global else "grantee"


def _build_utilities_surface_context(
    *,
    surface_query: dict[str, str] | None,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    authority_db_file: str | Path | None,
    portal_instance_id: str,
    default_to_global: bool = False,
) -> dict[str, Any]:
    """Resolve grantee/domain selection + grantee_selector list for the
    utilities tool-exposure surface.

    Returns a dict with:
      - "ctx": the extension render context (grantee, domain, private_dir, ...)
        plus ``mode`` ("global" | "grantee"); in global mode ``grantee`` is an
        empty dict, ``domain`` is "", and the full roster rides in ``grantees``.
      - "grantee_selector": Phase 12h surface-level selector payload listing
        every available grantee with an `active` flag, prefixed by a synthetic
        "All — Overall" entry that engages global mode.
      - "mode": the resolved mode (so the surface payload builder can thread it
        into the subtab strip).

    ``default_to_global`` lets the Extensions surface default to the overall
    view while the Grantee-Profile surface keeps its single-grantee default
    (its ctx stays byte-identical to before, plus the additive ``mode`` key).
    """
    from MyCiteV2.instances._shared.runtime.operational_store import (
        load_grantee_profiles,
        resolve_selected_domain,
        resolve_selected_grantee,
    )

    query = dict(surface_query or {})
    mode = _resolve_utilities_mode(query, default_to_global=default_to_global)
    # The active extension's INNER subtab is the mode switch on the Extensions
    # surface: "per_grantee" → grantee mode (when a grantee is selected); any
    # other subtab (Overall/Manifest/Browse) → global. This makes "Overall" the
    # default per-extension view and routes per-grantee uniformly through the
    # subtab. Surfaces that never set extension_subtab (Grantee-Profile, legacy)
    # are unaffected.
    _subtab = _as_text(query.get("extension_subtab"))
    if _subtab:
        mode = (
            "grantee"
            if (_subtab == "per_grantee" and _as_text(query.get("selected_grantee_msn")))
            else "global"
        )
    tool_state = {
        "selected_grantee_msn": query.get("selected_grantee_msn", ""),
        "selected_domain": query.get("selected_domain", ""),
    }
    grantees = load_grantee_profiles(private_dir)

    if mode == "global":
        # Overall / no-grantee view: every extension aggregates across the
        # whole roster instead of one grantee. grantee/domain are empty so a
        # per-grantee renderer takes its global branch; the roster rides in
        # ctx["grantees"] for aggregation.
        selected_grantee: dict[str, Any] = {}
        selected_msn = ""
        domain = ""
    else:
        selected_grantee = resolve_selected_grantee(grantees, tool_state)
        selected_msn = _as_text(selected_grantee.get("msn_id"))
        domain = resolve_selected_domain(selected_grantee, tool_state)

    ctx: dict[str, Any] = {
        "grantee": selected_grantee,
        "domain": domain,
        "private_dir": private_dir,
        "webapps_root": webapps_root,
        "authority_db_file": authority_db_file,
        "portal_instance_id": portal_instance_id,
        "mode": mode,
    }
    if mode == "global":
        ctx["grantees"] = grantees

    # Per-extension inner-subtab + Browse drill-down state. Additive and verbatim
    # from surface_query: an extension renderer branches on its active subtab and
    # drill level without re-parsing the request; extensions that ignore these
    # keys render exactly as before. (Reusable convention — see _EXTENSION_SUBTABS.)
    ctx["surface_query"] = dict(query)
    ctx["extension_subtab"] = _as_text(query.get("extension_subtab"))
    ctx["browse_type"] = _as_text(query.get("browse_type"))
    ctx["browse_view"] = _as_text(query.get("browse_view"))
    ctx["browse_instance"] = _as_text(query.get("browse_instance"))

    # Phase 12h: surface-level grantee selector. Each entry carries the
    # transition payload the client posts to switch grantees. The shell-
    # request layer normalizes `selected_grantee_msn` into surface_query.
    # Each real entry also pins utilities_mode="grantee"; the synthetic first
    # entry engages global mode.
    overall_entry = {
        "msn_id": "",
        "label": "All — Overall",
        "short_name": "",
        "domains": [],
        "is_overall": True,
        "active": mode == "global",
        "select_action": {
            "route": "/portal/api/v2/shell",
            "schema": "mycite.v2.portal.shell.request.v1",
            "payload": {
                "requested_surface_id": UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
                "surface_query": {
                    "selected_grantee_msn": "",
                    "utilities_mode": "global",
                },
            },
        },
    }
    real_entries = [
        {
            "msn_id": _as_text(g.get("msn_id")),
            "label": _as_text(g.get("label")) or _as_text(g.get("msn_id")),
            "short_name": _as_text(g.get("short_name")),
            "domains": list(g.get("domains") or []),
            "active": mode == "grantee" and _as_text(g.get("msn_id")) == selected_msn,
            "select_action": {
                "route": "/portal/api/v2/shell",
                "schema": "mycite.v2.portal.shell.request.v1",
                "payload": {
                    "requested_surface_id": UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
                    "surface_query": {
                        "selected_grantee_msn": _as_text(g.get("msn_id")),
                        "utilities_mode": "grantee",
                    },
                },
            },
        }
        for g in grantees
    ]
    # The synthetic "All — Overall" entry leads the list when there is at least
    # one grantee; with no grantees configured the list stays empty (Overall is
    # meaningless) so the empty-state help text shows.
    grantee_selector = {
        "label": "Grantee",
        "selected_grantee_msn": selected_msn,
        "mode": mode,
        "grantees": [overall_entry, *real_entries] if real_entries else [],
        "empty_message": "No grantees configured. Add a grantee JSON file under "
        "{private_dir}/utilities/tools/fnd-csm/grantee.*.json.",
    }
    return {"ctx": ctx, "grantee_selector": grantee_selector, "mode": mode}


def _build_utilities_extensions(
    *,
    tool_exposure_policy: dict[str, Any] | None,
    ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    """Phase 2 (portal_tool_surface_contract.md): render each enabled Utilities
    extension by calling its renderer. Returns a list of
    `{tool_id, label, summary, payload}` entries.

    Phase 12h split the grantee context resolution into
    `_build_utilities_surface_context` so the surface-level grantee selector
    can share the resolved selection without duplicating the load.

    Phase 14c: extensions read disjoint state (analytics → events dir,
    paypal → orders.ndjson, email → AWS profile store, newsletter → MOS
    contact log) so they can render in parallel. A ThreadPoolExecutor
    cuts wall-clock latency on cold-cache request paths; a soft per-
    extension timeout returns a ``degraded`` flag instead of blocking
    the whole bundle.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeoutError

    from MyCiteV2.instances._shared.runtime.utilities_extensions import (
        EXTENSION_RENDERERS,
        render_extension,
    )

    extension_entries = [
        entry for entry in build_portal_tool_registry_entries() if entry.is_extension
    ]
    eligible_entries = [
        entry
        for entry in extension_entries
        if entry.tool_id in EXTENSION_RENDERERS
        and _extension_enabled(tool_exposure_policy, entry.tool_id)
    ]
    if not eligible_entries:
        return []

    out: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, len(eligible_entries))) as pool:
        futures = {
            pool.submit(render_extension, entry.tool_id, ctx): entry
            for entry in eligible_entries
        }
        for entry in eligible_entries:
            future = next(f for f, e in futures.items() if e is entry)
            try:
                payload = future.result(timeout=5.0)
                out.append(
                    {
                        "tool_id": entry.tool_id,
                        "label": entry.label,
                        "summary": entry.summary,
                        "payload": payload,
                    }
                )
            except FuturesTimeoutError:
                out.append(
                    {
                        "tool_id": entry.tool_id,
                        "label": entry.label,
                        "summary": entry.summary,
                        "payload": {
                            "degraded": True,
                            "notice": (
                                f"{entry.label} did not respond within 5s; "
                                "rendering a placeholder. Check the extension's "
                                "data source."
                            ),
                        },
                    }
                )
            except Exception as exc:  # pragma: no cover - resilience
                out.append(
                    {
                        "tool_id": entry.tool_id,
                        "label": entry.label,
                        "summary": entry.summary,
                        "payload": {
                            "degraded": True,
                            "notice": f"{entry.label} failed to render: {exc}",
                        },
                    }
                )
    return out


def _extension_enabled(
    tool_exposure_policy: dict[str, Any] | None, tool_id: str
) -> bool:
    """Honor an explicit per-tool enable flag in tool_exposure_policy; default to
    enabled when no policy entry exists (legacy FND-CSM tabs were always shown)."""
    if not isinstance(tool_exposure_policy, dict):
        return True
    entry = tool_exposure_policy.get(tool_id)
    if isinstance(entry, dict) and "enabled" in entry:
        return bool(entry["enabled"])
    return True


def _surface_payload_for_tool_exposure(
    tool_rows: list[dict[str, Any]],
    extensions: list[dict[str, Any]] | None = None,
    grantee_selector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": surface_schema_for_surface(UTILITIES_TOOL_EXPOSURE_SURFACE_ID),
        "kind": "tool_exposure",
        "title": "Tool Exposure",
        "subtitle": "Visibility, configuration, and enablement are managed under UTILITIES.",
        "sections": [
            {
                "title": "Tool posture",
                "columns": [
                    {"key": "tool", "label": "Tool"},
                    {"key": "configured", "label": "Configured"},
                    {"key": "enabled", "label": "Enabled"},
                    {"key": "operational", "label": "Operational"},
                ],
                "items": _rows_for_tool_table(tool_rows),
            }
        ],
    }
    # Phase 2 (portal_tool_surface_contract.md): per-extension structured payloads
    # produced by render_extension. Phase 3 will consume these client-side
    # via the palette UI.
    if extensions:
        payload["extensions"] = extensions
    # Phase 12h: surface-level grantee selector. Lets operators switch the
    # grantee context that drives every extension below without leaving the
    # Utilities tab.
    if grantee_selector is not None:
        payload["grantee_selector"] = grantee_selector
    return payload


# Phase 14b: four dedicated surface payloads that replace the single
# tool-exposure surface mixing tools + extensions + grantee profile.
# Each one is scoped to one operator concern.


def _surface_payload_for_extensions(
    extensions: list[dict[str, Any]] | None = None,
    grantee_selector: dict[str, Any] | None = None,
    *,
    selected_extension_tool_id: str = "",
    extension_subtab: str = "",
    mode: str = "grantee",
) -> dict[str, Any]:
    """Operational utilities-tab extensions only (Email, Analytics,
    Newsletter, PayPal). Grantee Profile is hosted by its own surface.

    Phase 15a: the surface now carries an ``extension_subtab_selector``
    sitting below the grantee_selector. Only the active tab's
    extension card lands in ``payload["extensions"]`` — the others are
    available behind clicks that POST back to /portal/api/v2/shell.

    ``mode`` ("global" | "grantee") is the resolved overall-vs-per-grantee
    view; it is threaded into the subtab strip so switching extension tabs
    stays in the current mode, and exposed in the payload for the client.
    """
    payload: dict[str, Any] = {
        "schema": surface_schema_for_surface(UTILITIES_EXTENSIONS_SURFACE_ID),
        "kind": "extensions",
        "mode": mode,
        "title": "Extensions",
        "subtitle": (
            "Each extension opens on its Overall view across all grantees; use "
            "its Per-grantee subtab to manage one grantee. Switch extensions with "
            "the tab strip below."
        ),
    }
    operational = [
        ext for ext in (extensions or []) if ext.get("tool_id") != "ext_grantee_profile"
    ]
    active_tool_id = _resolve_selected_extension_tool_id(
        operational, _as_text(selected_extension_tool_id)
    )
    selected_grantee_msn = (
        _as_text((grantee_selector or {}).get("selected_grantee_msn"))
        if grantee_selector
        else ""
    )
    # The surface-level grantee selector is RETIRED for the Extensions surface:
    # per-grantee is reached via each extension's "Per-grantee" inner subtab, which
    # hosts the grantee picker. "Overall" is the default view. (The Grantee-Profile
    # surface keeps its own selector — it is a different surface payload builder.)
    if operational:
        payload["extension_subtab_selector"] = _build_extension_subtab_selector(
            operational,
            active_tool_id,
            selected_grantee_msn=selected_grantee_msn,
            utilities_mode=mode,
            extension_subtab=_as_text(extension_subtab),
        )
        active_entries = [
            ext for ext in operational if _as_text(ext.get("tool_id")) == active_tool_id
        ]
        if active_entries and active_tool_id in _EXTENSION_SUBTABS:
            active_subtab = _resolve_inner_subtab(active_tool_id, _as_text(extension_subtab))
            entry = active_entries[0]
            # Per-grantee subtab with NO grantee chosen yet: show only the picker +
            # a prompt, not the Overall payload render_extension produced under
            # global mode. Resources returns its own prompt — don't clobber it.
            if active_subtab == "per_grantee" and not selected_grantee_msn:
                cur = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
                # Keep a degraded/timeout payload (its ``notice`` is the only signal
                # that the extension's data source is down) — never mask it with the
                # generic prompt. Resources returns its own prompt — don't clobber.
                if not cur.get("per_grantee_prompt") and not cur.get("degraded"):
                    entry["payload"] = {
                        "per_grantee_prompt": (
                            f"Select a grantee to manage "
                            f"{_as_text(entry.get('label')) or 'this extension'} for one grantee."
                        )
                    }
            entry_payload = entry.get("payload")
            if isinstance(entry_payload, dict):
                entry_payload["inner_subtab_selector"] = _build_inner_subtab_selector(
                    active_tool_id,
                    active_subtab,
                    selected_grantee_msn=selected_grantee_msn,
                    utilities_mode=mode,
                )
                # Host the grantee picker in-card on the Per-grantee subtab. Drop
                # the synthetic "All — Overall" entry — the Overall subtab is the
                # way back to the global view.
                if active_subtab == "per_grantee" and grantee_selector is not None:
                    picker = _grantee_selector_for_target(
                        grantee_selector,
                        UTILITIES_EXTENSIONS_SURFACE_ID,
                        preserved_query={
                            "selected_extension_tool_id": active_tool_id,
                            "extension_subtab": "per_grantee",
                        },
                    )
                    picker["grantees"] = [
                        g for g in (picker.get("grantees") or []) if not g.get("is_overall")
                    ]
                    entry_payload["grantee_picker"] = picker
        payload["extensions"] = active_entries
    else:
        # No operational extensions enabled → emit an empty-state section so the
        # workbench content-probe still recognizes the surface (the retired
        # grantee_selector used to be that signal) and renders this message
        # instead of blanking to "This tool does not provide a workbench view."
        payload["sections"] = [
            {
                "title": "Extensions",
                "rows": [
                    {
                        "label": "status",
                        "detail": "No operational extensions are enabled for this portal.",
                    }
                ],
            }
        ]
    return payload


def _surface_payload_for_grantee_profile(
    extensions: list[dict[str, Any]] | None = None,
    grantee_selector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grantee Profile editor surface. Hosts only the grantee selector +
    the ext_grantee_profile form_frame — none of the operational
    extensions live here.
    """
    payload: dict[str, Any] = {
        "schema": surface_schema_for_surface(UTILITIES_GRANTEE_PROFILE_SURFACE_ID),
        "kind": "grantee_profile",
        "title": "Grantee Profile",
        "subtitle": (
            "The single source of truth for every extension's credentials, "
            "domains, and operator mailbox list."
        ),
    }
    if grantee_selector is not None:
        payload["grantee_selector"] = _grantee_selector_for_target(
            grantee_selector, UTILITIES_GRANTEE_PROFILE_SURFACE_ID
        )
    profile_only = [
        ext for ext in (extensions or []) if ext.get("tool_id") == "ext_grantee_profile"
    ]
    if profile_only:
        payload["extensions"] = profile_only
    return payload


def _surface_payload_for_tools(tool_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Tools posture/configuration surface. Lists only entries where
    ``is_extension=False``, filters out ``workbench_ui`` (a SYSTEM tool
    that should never appear under Utilities), leaving CTS-GIS (and
    future AGRO-ERP) as the operator-facing tool catalog.
    """
    excluded_tool_ids = {"workbench_ui"}
    filtered_rows = [
        row
        for row in tool_rows
        if not row.get("is_extension")
        and row.get("tool_id") not in excluded_tool_ids
    ]
    return {
        "schema": surface_schema_for_surface(UTILITIES_TOOLS_SURFACE_ID),
        "kind": "tools",
        "title": "Tools",
        "subtitle": (
            "First-class palette tools that visualize MOS datum data in "
            "particular ways. Tools may be grayed out when required datum "
            "archetypes are absent."
        ),
        "sections": [
            {
                "title": "Tool posture",
                "columns": [
                    {"key": "tool", "label": "Tool"},
                    {"key": "configured", "label": "Configured"},
                    {"key": "enabled", "label": "Enabled"},
                    {"key": "operational", "label": "Operational"},
                ],
                "items": _rows_for_tool_table(filtered_rows),
            }
        ],
    }


def _surface_payload_for_peripherals() -> dict[str, Any]:
    """Live landing for peripherals.

    The AWS peripheral (`MyCiteV2.packages.peripherals.aws`) is queried
    per-domain for the active grantee; each domain's status becomes a
    card. Keypass vault and TLS health are still placeholders — they
    are independent peripherals not yet implemented.

    Best-effort: failures inside the peripheral are caught and surfaced
    as note text rather than raising; the Utilities surface should
    never 500 because of a degraded AWS state.
    """
    aws_cards: list[dict[str, Any]] = []
    aws_notes: list[str] = []
    try:
        from MyCiteV2.packages.peripherals.aws import (
            AwsPeripheralCloudAdapter,
            ProfileStore,
        )

        store = ProfileStore()
        adapter = AwsPeripheralCloudAdapter(profile_store=store)
        for domain in store.domains():
            try:
                status = adapter.describe_domain_status(domain)
                summary = []
                if status["ses_identity_verified"]:
                    summary.append("SES verified")
                if status["dkim_verified"]:
                    summary.append("DKIM verified")
                if status["mx_present"]:
                    summary.append("MX")
                if status["spf_present"]:
                    summary.append("SPF")
                if status["dmarc_present"]:
                    summary.append("DMARC")
                if status["receipt_rule_present"]:
                    summary.append("receipt rule")
                if not summary:
                    summary.append("(not configured)")
                aws_cards.append(
                    {
                        "label": f"AWS · {domain}",
                        "value": " / ".join(summary),
                    }
                )
            except Exception as exc:
                aws_notes.append(f"{domain}: error: {exc}")
    except Exception as exc:
        aws_notes.append(f"aws peripheral unavailable: {exc}")

    cards: list[dict[str, Any]] = [
        *aws_cards,
        {"label": "Keypass vault", "value": "Pending"},
        {"label": "TLS / cert health", "value": "Pending"},
    ]
    notes: list[str] = [
        *aws_notes,
        "AWS peripheral status from peripherals.aws.describe_domain_status.",
        "Keypass + TLS surfaces are independent peripherals not yet implemented.",
        "Operational integration readiness is also reported by /portal/healthz "
        "(authority_db, static_files_present, shell_asset_manifest).",
    ]
    return {
        "schema": surface_schema_for_surface(UTILITIES_PERIPHERALS_SURFACE_ID),
        "kind": "peripherals",
        "title": "Peripherals",
        "subtitle": "AWS peripheral status by domain, plus pending Keypass and TLS surfaces.",
        "cards": cards,
        "notes": notes,
    }


def _grantee_selector_for_target(
    grantee_selector: dict[str, Any],
    target_surface_id: str,
    *,
    preserved_query: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Rewrite a grantee selector built by `_build_utilities_surface_context`
    so each option's ``select_action`` posts back to the given surface.
    The base context builder hard-codes the tool-exposure surface (Phase
    12h was authored when that was the only utilities surface); Phase 14b
    needs the selector to navigate within its own surface.

    Phase 15a: ``preserved_query`` carries extra ``surface_query`` keys
    (e.g. the active ``selected_extension_tool_id``) that must survive a
    grantee switch — without it, clicking a grantee would reset the
    active extension tab to the default.
    """
    extras = dict(preserved_query or {})
    rewritten: dict[str, Any] = dict(grantee_selector)
    rewritten["grantees"] = [
        {
            **g,
            "select_action": {
                **g.get("select_action", {}),
                "payload": {
                    **(g.get("select_action", {}).get("payload") or {}),
                    "requested_surface_id": target_surface_id,
                    "surface_query": {
                        **(g.get("select_action", {}).get("payload") or {}).get(
                            "surface_query", {}
                        ),
                        **extras,
                    },
                },
            },
        }
        for g in (grantee_selector.get("grantees") or [])
    ]
    return rewritten


# Phase 15a — per-extension subtabs on the Extensions surface.
# Order is the operator-facing tab order, left to right.
# Phase 17b: ext_connect joins as the 5th tab (visitor messages
# forwarded via SES, lead-collection sibling to the newsletter).
_OPERATIONAL_EXTENSION_ORDER: tuple[str, ...] = (
    "ext_aws_email",
    "ext_analytics",
    "ext_newsletter",
    "ext_paypal",
    "ext_connect",
    # Wave 2: the resources asset-library extension (profiles contact-app,
    # galleries, icon dedup). Not grantee-scoped, but lives on the same
    # Extensions surface tab strip as the operational extensions.
    "ext_resources",
)
_OPERATIONAL_EXTENSION_DEFAULT = "ext_aws_email"


def _resolve_selected_extension_tool_id(
    extensions: list[dict[str, Any]] | None,
    requested_tool_id: str,
) -> str:
    """Pick the active extension tab. Honors the request when it names a
    known operational extension; otherwise falls back to the leftmost
    extension present in ``extensions`` (or ext_aws_email).
    """
    available = {
        _as_text(ext.get("tool_id"))
        for ext in (extensions or [])
        if _as_text(ext.get("tool_id")) in _OPERATIONAL_EXTENSION_ORDER
    }
    if requested_tool_id in available:
        return requested_tool_id
    for tool_id in _OPERATIONAL_EXTENSION_ORDER:
        if tool_id in available:
            return tool_id
    return _OPERATIONAL_EXTENSION_DEFAULT


def _build_extension_subtab_selector(
    extensions: list[dict[str, Any]] | None,
    selected_tool_id: str,
    *,
    selected_grantee_msn: str,
    utilities_mode: str = "grantee",
    extension_subtab: str = "",
) -> dict[str, Any]:
    """Build the per-extension tab strip (Email/Analytics/.../Resources). Each
    tab's ``select_action`` posts to /portal/api/v2/shell preserving the current
    grantee, the overall-vs-per-grantee ``utilities_mode``, AND the active inner
    ``extension_subtab`` — so switching the extension keeps the inner subtab
    (Overall/Per-grantee) highlight in sync with the rendered content.
    """
    by_tool_id = {
        _as_text(ext.get("tool_id")): ext for ext in (extensions or []) if isinstance(ext, dict)
    }
    tabs: list[dict[str, Any]] = []
    for tool_id in _OPERATIONAL_EXTENSION_ORDER:
        ext = by_tool_id.get(tool_id)
        if ext is None:
            continue
        tabs.append(
            {
                "tool_id": tool_id,
                "label": _as_text(ext.get("label")) or tool_id,
                "summary": _as_text(ext.get("summary")),
                "active": tool_id == selected_tool_id,
                "select_action": {
                    "route": "/portal/api/v2/shell",
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "payload": {
                        "requested_surface_id": UTILITIES_EXTENSIONS_SURFACE_ID,
                        "surface_query": {
                            "selected_grantee_msn": selected_grantee_msn,
                            "selected_extension_tool_id": tool_id,
                            "utilities_mode": utilities_mode,
                            # Preserve the active inner subtab so switching the
                            # extension keeps the Overall/Per-grantee highlight in
                            # sync with the rendered content (the target extension
                            # resolves it to its own default if it has no match).
                            "extension_subtab": extension_subtab,
                        },
                    },
                },
            }
        )
    return {
        "label": "Extension",
        "selected_tool_id": selected_tool_id,
        "tabs": tabs,
        "empty_message": "No operational extensions are enabled for this grantee.",
    }


# Per-extension INNER subtabs (Phase: resource type browser). The active subtab
# rides surface_query["extension_subtab"]; an extension absent from this map
# renders with no inner strip (unchanged). The reusable convention: an extension
# declares ordered subtabs here, the shell builds the strip, and the extension
# renderer produces only the active subtab's CONTENT (branching on
# ctx["extension_subtab"], defaulting to the first id).
# Every operational extension gets the same convention: an "Overall" (global)
# view that is the DEFAULT, plus a "Per-grantee" subtab that hosts the grantee
# picker + that extension's per-grantee view. Resources keeps richer overall
# subtabs (Manifest/Browse). The first id is the default subtab.
_DEFAULT_EXTENSION_SUBTABS: tuple[dict[str, str], ...] = (
    {"id": "overall", "label": "Overall"},
    {"id": "per_grantee", "label": "Per-grantee"},
)
_EXTENSION_SUBTABS: dict[str, tuple[dict[str, str], ...]] = {
    "ext_aws_email": _DEFAULT_EXTENSION_SUBTABS,
    "ext_analytics": _DEFAULT_EXTENSION_SUBTABS,
    "ext_newsletter": _DEFAULT_EXTENSION_SUBTABS,
    "ext_paypal": _DEFAULT_EXTENSION_SUBTABS,
    "ext_connect": _DEFAULT_EXTENSION_SUBTABS,
    "ext_resources": (
        {"id": "manifest", "label": "Manifest"},
        {"id": "browse", "label": "Browse"},
        {"id": "per_grantee", "label": "Per-grantee"},
    ),
}


def _resolve_inner_subtab(tool_id: str, requested: str) -> str:
    """The active inner subtab id: the request when it names a declared subtab,
    else the first declared subtab, else "" (no subtabs)."""
    subtabs = _EXTENSION_SUBTABS.get(tool_id) or ()
    if any(sub["id"] == requested for sub in subtabs):
        return requested
    return subtabs[0]["id"] if subtabs else ""


def _build_inner_subtab_selector(
    tool_id: str,
    active_subtab: str,
    *,
    selected_grantee_msn: str,
    utilities_mode: str,
) -> dict[str, Any]:
    """Inner subtab strip for one extension card. Mirrors
    ``_build_extension_subtab_selector`` but emits ``extension_subtab`` per tab
    and keeps the active extension + grantee + mode pinned. Switching subtabs
    drops the Browse drill-down (browse_type/view/instance omitted → reset)."""
    tabs: list[dict[str, Any]] = []
    for sub in _EXTENSION_SUBTABS.get(tool_id) or ():
        sub_id = sub["id"]
        tabs.append(
            {
                "id": sub_id,
                "label": sub.get("label") or sub_id,
                "active": sub_id == active_subtab,
                "select_action": {
                    "route": "/portal/api/v2/shell",
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "payload": {
                        "requested_surface_id": UTILITIES_EXTENSIONS_SURFACE_ID,
                        "surface_query": {
                            "selected_grantee_msn": selected_grantee_msn,
                            "selected_extension_tool_id": tool_id,
                            # The subtab IS the mode switch: Per-grantee engages
                            # grantee mode; every other subtab (Overall/Manifest/
                            # Browse) engages global mode — so "Overall" is the
                            # default and per-grantee is reached via the subtab.
                            "utilities_mode": "grantee" if sub_id == "per_grantee" else "global",
                            "extension_subtab": sub_id,
                        },
                    },
                },
            }
        )
    return {"label": "View", "selected_subtab": active_subtab, "tabs": tabs}


def _generic_workbench(surface_payload: dict[str, Any], *, visible: bool = True) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
        "kind": "surface_payload",
        "title": _as_text(surface_payload.get("title")) or "Surface",
        "subtitle": _as_text(surface_payload.get("subtitle")),
        "visible": visible,
        "surface_payload": surface_payload,
    }


def _surface_render_error_bundle(*, surface_id: str, detail: str) -> dict[str, Any]:
    """Pure, no-I/O fallback bundle for when one surface's render raises. It keeps
    the shell chrome alive and confines the failure to the workbench pane. The
    envelope-level error is deliberately left UNSET so ``_runtime_response`` stays
    HTTP 200 — a non-200 makes the JS shell ``showFatal`` and blank the whole
    portal. The message therefore rides inside the surface_payload's ``sections``
    (what the generic surface renderer displays), never the envelope error. Built
    only from pure helpers, so this fallback can never itself raise."""
    error_payload = {
        "schema": surface_schema_for_surface(surface_id),
        "kind": "surface_render_error",
        "title": "This surface could not be rendered",
        "subtitle": "The rest of the portal is available — pick another surface or reload.",
        "sections": [
            {
                "title": "Surface unavailable",
                "rows": [{"label": "detail", "detail": _as_text(detail) or "Render failed."}],
            }
        ],
    }
    return {
        "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": "Unavailable",
        "page_subtitle": "This surface could not be rendered.",
        "surface_payload": error_payload,
        "control_panel": attach_region_family_contract(
            _utilities_control_panel(active_surface_id=surface_id),
            family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
            surface_id=surface_id,
        ),
        "workbench": attach_region_family_contract(
            _generic_workbench(error_payload),
            family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
            surface_id=surface_id,
        ),
        "tool_rows": [],
    }


ToolSurfaceBundleBuilder = Callable[..., dict[str, Any]]


def _build_workbench_ui_tool_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: PortalShellState | None,
    authority_db_file: str | Path | None,
    tool_rows: list[dict[str, Any]],
    surface_query: dict[str, str] | None,
    private_dir: str | Path | None = None,
    **_: Any,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_lens_runtime import enabled_lens_ids
    from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
        build_portal_workbench_ui_bundle,
    )

    return build_portal_workbench_ui_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=shell_state,
        authority_db_file=authority_db_file,
        tool_rows=tool_rows,
        surface_query=surface_query,
        # Apply the operator's Control-Panel lens toggles (disabled → identity).
        # private_dir flows in via _tool_bundle_for_surface; None ⇒ all enabled.
        enabled_lens_ids=enabled_lens_ids(private_dir),
    )


def _build_agro_erp_tool_bundle(
    *,
    portal_scope: PortalScope,
    portal_domain: str,
    shell_state: PortalShellState | None,
    authority_db_file: str | Path | None,
    tool_rows: list[dict[str, Any]],
    surface_query: dict[str, str] | None,
    **_: Any,
) -> dict[str, Any]:
    from MyCiteV2.instances._shared.runtime.portal_agro_erp_runtime import (
        build_portal_agro_erp_surface_bundle,
    )

    return build_portal_agro_erp_surface_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=shell_state,
        authority_db_file=authority_db_file,
        tool_rows=tool_rows,
        surface_query=surface_query,
    )


_TOOL_SURFACE_BUNDLE_BUILDERS: dict[str, ToolSurfaceBundleBuilder] = {
    WORKBENCH_UI_TOOL_SURFACE_ID: _build_workbench_ui_tool_bundle,
    AGRO_ERP_TOOL_SURFACE_ID: _build_agro_erp_tool_bundle,
}

_RUNTIME_OWNED_TOOL_SURFACE_IDS = frozenset(
    {
        WORKBENCH_UI_TOOL_SURFACE_ID,
        AGRO_ERP_TOOL_SURFACE_ID,
    }
)


def _tool_shell_state(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
) -> PortalShellState | None:
    if surface_id in _RUNTIME_OWNED_TOOL_SURFACE_IDS:
        return None
    return canonicalize_portal_shell_state(
        shell_state,
        active_surface_id=surface_id,
        portal_scope=portal_scope,
        seed_anchor_file=shell_state is None,
    )


def _tool_bundle_for_surface(
    *,
    surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    request_payload: dict[str, Any] | None,
    surface_query: dict[str, str] | None,
    data_dir: str | Path | None,
    private_dir: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    tool_rows: list[dict[str, Any]],
    portal_domain: str,
    authority_db_file: str | Path | None,
) -> dict[str, Any]:
    builder = _TOOL_SURFACE_BUNDLE_BUILDERS.get(surface_id)
    if builder is None:
        raise ValueError(f"Unsupported tool surface: {surface_id}")
    return builder(
        surface_id=surface_id,
        portal_scope=portal_scope,
        shell_state=shell_state,
        request_payload=request_payload,
        surface_query=surface_query,
        data_dir=data_dir,
        private_dir=private_dir,
        webapps_root=webapps_root,
        tool_exposure_policy=tool_exposure_policy,
        tool_rows=tool_rows,
        portal_domain=portal_domain,
        authority_db_file=authority_db_file,
    )


def _bundle_for_surface(
    *,
    selection_surface_id: str,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    request_payload: dict[str, Any] | None,
    surface_query: dict[str, str] | None,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    private_dir: str | Path | None,
    audit_storage_file: str | Path | None,
    webapps_root: str | Path | None,
    tool_exposure_policy: dict[str, Any] | None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    integration_flags = _integration_flags(
        data_dir=data_dir,
        webapps_root=webapps_root,
    )
    tool_rows = _tool_posture_rows(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        integration_flags=integration_flags,
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    if selection_surface_id == SYSTEM_ROOT_SURFACE_ID:
        # Plan v2: /portal/system delegates to the unified workbench so
        # the system page = the portal database view, parameterised by
        # the menubar sandbox selector. Default sandbox is "system" (the
        # reflective corpus-wide view). The workbench builder already
        # consumes surface_query.{sandbox_filter, mode, tool, document,
        # row}, so the system root needs no extra wiring beyond
        # delegation.
        from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
            build_portal_workbench_ui_bundle,
        )
        canonical_state = canonicalize_portal_shell_state(
            shell_state,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=portal_scope,
            seed_anchor_file=shell_state is None,
        )
        from MyCiteV2.instances._shared.runtime.portal_lens_runtime import (
            enabled_lens_ids as _enabled_lens_ids,
        )
        bundle = build_portal_workbench_ui_bundle(
            portal_scope=portal_scope,
            portal_domain=portal_domain,
            shell_state=canonical_state,
            authority_db_file=authority_db_file,
            tool_rows=tool_rows,
            surface_query=surface_query,
            # Apply the operator's Control-Panel lens toggles on the /portal/system
            # landing surface too (previously all-enabled regardless of toggles).
            enabled_lens_ids=_enabled_lens_ids(private_dir),
        )
        # The workbench bundle stamps WORKBENCH_UI identifiers on the
        # surface_payload; rewrite them for the SYSTEM root so
        # downstream consumers (envelope schema asserts, JS routing)
        # still see system-root identity. This includes the
        # family_contract.surface_id that attach_region_family_contract
        # stamps on each region — JS routes region actions off that
        # field, and from the user's perspective the active surface is
        # /portal/system, not /portal/system/tools/workbench-ui.
        payload = bundle.setdefault("surface_payload", {})
        payload["kind"] = "system_workspace"
        bundle["entrypoint_id"] = PORTAL_SHELL_ENTRYPOINT_ID
        bundle["route"] = SYSTEM_ROOT_ROUTE
        bundle["tool_rows"] = tool_rows
        for _region_key in ("control_panel", "workbench", "interface_panel"):
            _region = bundle.get(_region_key)
            if not isinstance(_region, dict):
                continue
            _contract = _region.get("family_contract")
            if isinstance(_contract, dict) and _contract.get("surface_id"):
                _contract["surface_id"] = SYSTEM_ROOT_SURFACE_ID
        return bundle
    if selection_surface_id in _TOOL_SURFACE_BUNDLE_BUILDERS:
        bundle = _tool_bundle_for_surface(
            surface_id=selection_surface_id,
            portal_scope=portal_scope,
            shell_state=_tool_shell_state(
                surface_id=selection_surface_id,
                portal_scope=portal_scope,
                shell_state=shell_state,
            ),
            request_payload=request_payload,
            surface_query=surface_query,
            data_dir=data_dir,
            private_dir=private_dir,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
            tool_rows=tool_rows,
            portal_domain=portal_domain,
            authority_db_file=authority_db_file,
        )
        bundle["tool_rows"] = tool_rows
        return bundle
    if selection_surface_id == NETWORK_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_network(
            portal_instance_id=portal_scope.scope_id,
            portal_domain=portal_domain,
            data_dir=data_dir,
            private_dir=private_dir,
            audit_storage_file=audit_storage_file,
            surface_query=surface_query,
        )
        return {
            "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "page_title": "Network",
            "page_subtitle": "Portal-instance system-log workbench.",
            "surface_payload": surface_payload,
            "control_panel": attach_region_family_contract(
                _network_control_panel(
                    portal_scope=portal_scope,
                    shell_state=shell_state,
                    active_surface_id=selection_surface_id,
                    surface_payload=surface_payload,
                ),
                family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
                surface_id=selection_surface_id,
            ),
            "workbench": attach_region_family_contract(
                _network_workbench(surface_payload),
                family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
                surface_id=selection_surface_id,
            ),
            "tool_rows": tool_rows,
        }
    if selection_surface_id == UTILITIES_ROOT_SURFACE_ID:
        surface_payload = _surface_payload_for_utilities_root(tool_rows)
        return {
            "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
            "read_write_posture": "read-only",
            "page_title": "Utilities",
            "page_subtitle": "Configuration and control surfaces.",
            "surface_payload": surface_payload,
            "control_panel": attach_region_family_contract(
                _utilities_control_panel(
                    active_surface_id=selection_surface_id,
                ),
                family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
                surface_id=selection_surface_id,
            ),
            "workbench": attach_region_family_contract(
                _generic_workbench(surface_payload),
                family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
                surface_id=selection_surface_id,
            ),
            "tool_rows": tool_rows,
        }
    if selection_surface_id in {
        UTILITIES_TOOL_EXPOSURE_SURFACE_ID,
        UTILITIES_EXTENSIONS_SURFACE_ID,
        UTILITIES_GRANTEE_PROFILE_SURFACE_ID,
    }:
        # Phase 12h: resolve grantee/domain once, share between the
        # surface-level selector and the per-extension ctx.
        ctx_bundle = _build_utilities_surface_context(
            surface_query=surface_query,
            private_dir=private_dir,
            webapps_root=webapps_root,
            authority_db_file=authority_db_file,
            portal_instance_id=portal_scope.scope_id,
            # The Extensions surface defaults to the overall (all-grantees)
            # view; the Grantee-Profile + legacy tool-exposure surfaces keep
            # their single-grantee default so their behavior is unchanged.
            default_to_global=selection_surface_id == UTILITIES_EXTENSIONS_SURFACE_ID,
        )
        extensions = _build_utilities_extensions(
            tool_exposure_policy=tool_exposure_policy,
            ctx=ctx_bundle["ctx"],
        )
        if selection_surface_id == UTILITIES_EXTENSIONS_SURFACE_ID:
            surface_payload = _surface_payload_for_extensions(
                extensions=extensions,
                grantee_selector=ctx_bundle["grantee_selector"],
                selected_extension_tool_id=_as_text(
                    (surface_query or {}).get("selected_extension_tool_id")
                ),
                extension_subtab=_as_text((surface_query or {}).get("extension_subtab")),
                mode=_as_text(ctx_bundle.get("mode")) or "grantee",
            )
        elif selection_surface_id == UTILITIES_GRANTEE_PROFILE_SURFACE_ID:
            surface_payload = _surface_payload_for_grantee_profile(
                extensions=extensions,
                grantee_selector=ctx_bundle["grantee_selector"],
            )
        else:
            # Legacy tool-exposure surface kept for one transition cycle so
            # external bookmarks resolve. Phase 14b's app.py 302-redirects
            # this route to /portal/utilities/extensions.
            surface_payload = _surface_payload_for_tool_exposure(
                tool_rows,
                extensions=extensions,
                grantee_selector=ctx_bundle["grantee_selector"],
            )
    elif selection_surface_id == UTILITIES_TOOLS_SURFACE_ID:
        surface_payload = _surface_payload_for_tools(tool_rows)
    else:
        # All remaining UTILITIES_SURFACE_IDS resolve to the peripherals
        # landing. Phase 14e (cleanup): the legacy integrations surface
        # payload builder was removed, so callers requesting
        # ``utilities.integrations`` directly via the API now receive
        # the peripherals payload. The HTTP route at /portal/utilities/
        # integrations 302-redirects regardless, so this only affects
        # API clients that hand-craft surface_id requests.
        surface_payload = _surface_payload_for_peripherals()
    return {
        "entrypoint_id": PORTAL_SHELL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": _as_text(surface_payload.get("title")) or "Utilities",
        "page_subtitle": _as_text(surface_payload.get("subtitle")),
        "surface_payload": surface_payload,
        "control_panel": attach_region_family_contract(
            _utilities_control_panel(
                active_surface_id=selection_surface_id,
            ),
            family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
            surface_id=selection_surface_id,
        ),
        "workbench": attach_region_family_contract(
            _generic_workbench(surface_payload),
            family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
            surface_id=selection_surface_id,
        ),
        "tool_rows": tool_rows,
    }


def run_portal_shell_entry(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None = None,
    public_dir: str | Path | None = None,
    private_dir: str | Path | None = None,
    audit_storage_file: str | Path | None = None,
    webapps_root: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    normalized_request = _normalize_request(
        request_payload,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
        tool_exposure_policy=tool_exposure_policy,
    )
    selection = resolve_portal_shell_request(normalized_request)
    portal_scope = normalized_request.portal_scope
    render_warnings: list[dict[str, Any]] = []
    try:
        bundle = _bundle_for_surface(
            selection_surface_id=selection.active_surface_id,
            portal_scope=portal_scope,
            shell_state=selection.shell_state,
            request_payload=request_payload,
            surface_query=normalized_request.surface_query,
            portal_domain=portal_domain,
            data_dir=data_dir,
            public_dir=public_dir,
            private_dir=private_dir,
            audit_storage_file=audit_storage_file,
            webapps_root=webapps_root,
            tool_exposure_policy=tool_exposure_policy,
            authority_db_file=authority_db_file,
            authority_mode=authority_mode,
        )
    except Exception as exc:
        # A single surface's render failure must NOT 500 the shell endpoint (which
        # blanks the entire portal). Degrade to a chrome-intact fallback that shows
        # the error only in this surface's pane. Re-raise the one error the
        # /portal/api/v2/shell handler special-cases so its behaviour is preserved.
        if getattr(exc, "code", "") == "legacy_maps_alias_unsupported":
            raise
        _log.exception(
            "portal_shell_surface_render_failed surface=%s", selection.active_surface_id
        )
        bundle = _surface_render_error_bundle(
            surface_id=selection.active_surface_id,
            detail="This surface could not be rendered.",
        )
        render_warnings.append(
            {"code": "surface_render_failed", "surface_id": selection.active_surface_id}
        )
    canonical_route = _as_text(bundle.get("canonical_route")) or selection.canonical_route
    canonical_query = dict(bundle.get("canonical_query") or selection.canonical_query)
    canonical_url = _as_text(bundle.get("canonical_url")) or build_canonical_url(
        surface_id=selection.active_surface_id,
        query=canonical_query,
    )
    composition_shell_state = selection.shell_state if selection.reducer_owned else None
    composition = build_shell_composition_payload(
        active_surface_id=selection.active_surface_id,
        portal_instance_id=portal_scope.scope_id,
        page_title=bundle["page_title"],
        page_subtitle=bundle["page_subtitle"],
        activity_items=_activity_items(
            portal_scope=portal_scope,
            active_surface_id=selection.active_surface_id,
            shell_state=composition_shell_state,
        ),
        control_panel=bundle["control_panel"],
        workbench=bundle["workbench"],
        interface_panel=bundle.get("interface_panel"),
        shell_state=composition_shell_state,
        control_panel_collapsed=bool(
            composition_shell_state.chrome.control_panel_collapsed if composition_shell_state is not None else False
        ),
    )
    error = None
    if not selection.allowed:
        error = build_portal_runtime_error(
            code=selection.reason_code or "surface_unknown",
            message=selection.reason_message or "Requested surface is not available.",
        )
    elif selection.active_surface_id in SYSTEM_SURFACE_IDS:
        error = _sql_runtime_error_for_surface(
            surface_id=selection.active_surface_id,
            portal_instance_id=portal_scope.scope_id,
            authority_db_file=authority_db_file,
        )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=selection.requested_surface_id,
        surface_id=selection.active_surface_id,
        entrypoint_id=bundle["entrypoint_id"],
        read_write_posture=bundle["read_write_posture"],
        reducer_owned=selection.reducer_owned,
        canonical_route=canonical_route,
        canonical_query=canonical_query,
        canonical_url=canonical_url,
        shell_state=None if composition_shell_state is None else composition_shell_state.to_dict(),
        surface_payload=bundle["surface_payload"],
        shell_composition=composition,
        warnings=render_warnings,
        error=error,
    )


def run_system_profile_basics_action(
    request_payload: dict[str, Any] | None,
    *,
    portal_instance_id: str,
    portal_domain: str,
    data_dir: str | Path | None,
    public_dir: str | Path | None,
    audit_storage_file: str | Path | None = None,
    authority_db_file: str | Path | None = None,
    authority_mode: str = "sql_primary",
) -> dict[str, Any]:
    payload = dict(request_payload or {})
    if _as_text(payload.get("schema")) != SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {SYSTEM_WORKSPACE_PROFILE_BASICS_ACTION_REQUEST_SCHEMA}")
    _normalize_authority_mode(authority_mode)
    portal_scope = _portal_scope_from_request(
        payload,
        portal_instance_id=portal_instance_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
        tool_exposure_policy=None,
    )
    incoming_state = payload.get("shell_state")
    shell_state = (
        PortalShellState.from_value(incoming_state, portal_scope=portal_scope, fallback_surface_id=SYSTEM_ROOT_SURFACE_ID)
        if incoming_state is not None
        else None
    )
    if shell_state is None:
        shell_state = initial_portal_shell_state(
            surface_id=SYSTEM_ROOT_SURFACE_ID,
            portal_scope=portal_scope,
        )
    shell_state = canonicalize_portal_shell_state(
        shell_state,
        active_surface_id=SYSTEM_ROOT_SURFACE_ID,
        portal_scope=portal_scope,
        seed_anchor_file=False,
    )
    selection = resolve_portal_shell_request(
        {
            "schema": "mycite.v2.portal.shell.request.v1",
            "requested_surface_id": SYSTEM_ROOT_SURFACE_ID,
            "portal_scope": portal_scope.to_dict(),
            "shell_state": shell_state.to_dict(),
            "transition": {"kind": TRANSITION_FOCUS_FILE, "file_key": SYSTEM_PROFILE_BASICS_FILE_KEY},
        }
    )
    preexisting_error = _sql_runtime_error_for_surface(
        surface_id=SYSTEM_ROOT_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
    )
    authority_path = _path_or_none(authority_db_file)
    if preexisting_error is None and authority_path is not None:
        adapter = SqliteSystemDatumStoreAdapter(authority_path)
        if not adapter.has_publication_summary(portal_instance_id, portal_domain):
            preexisting_error = build_portal_runtime_error(
                code="sql_publication_summary_missing",
                message="The MOS SQL authority database is missing the publication summary required for profile updates.",
            )
    outcome = None
    if preexisting_error is None and authority_path is not None:
        adapter = SqliteSystemDatumStoreAdapter(authority_path)
        from MyCiteV2.packages.modules.domains.publication import PublicationProfileBasicsService

        outcome = PublicationProfileBasicsService(adapter).apply_write(
            {
                "tenant_id": portal_instance_id,
                "tenant_domain": portal_domain,
                "profile_title": payload.get("profile_title") or "",
                "profile_summary": payload.get("profile_summary") or "",
                "contact_email": payload.get("contact_email") or "",
                "public_website_url": payload.get("public_website_url") or "",
            }
        )
        try:
            from MyCiteV2.packages.modules.cross_domain.local_audit import LocalAuditService

            LocalAuditService(SqliteAuditLogAdapter(authority_path)).append_record(outcome.to_local_audit_payload())
        except Exception:
            _log.warning("system_profile_basics_audit_append_failed", exc_info=True)
            pass
    integration_flags = _integration_flags(
        data_dir=data_dir,
        webapps_root=None,
    )
    tool_rows = _tool_posture_rows(
        portal_scope=portal_scope,
        tool_exposure_policy=None,
        integration_flags=integration_flags,
        portal_instance_id=portal_scope.scope_id,
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    workspace_bundle = build_system_workspace_bundle(
        portal_scope=portal_scope,
        portal_domain=portal_domain,
        shell_state=selection.shell_state,
        data_dir=data_dir,
        public_dir=public_dir,
        audit_storage_file=audit_storage_file,
        tool_rows=tool_rows,
        profile_save_status="saved" if outcome is not None else "",
        authority_db_file=authority_db_file,
        authority_mode=authority_mode,
    )
    if outcome is not None:
        workspace_bundle["surface_payload"]["workspace"]["profile_basics"]["confirmed_summary"] = outcome.confirmed_summary.to_dict()
        # Ensure subsequent shell reads rebuild projection after write-side mutations.
        _invalidate_workbench_projection_cache(authority_db_file=authority_db_file)
    composition = build_shell_composition_payload(
        active_surface_id=SYSTEM_ROOT_SURFACE_ID,
        portal_instance_id=portal_scope.scope_id,
        page_title=workspace_bundle["page_title"],
        page_subtitle=workspace_bundle["page_subtitle"],
        activity_items=_activity_items(
            portal_scope=portal_scope,
            active_surface_id=SYSTEM_ROOT_SURFACE_ID,
            shell_state=selection.shell_state,
        ),
        control_panel=workspace_bundle["control_panel"],
        workbench=workspace_bundle["workbench"],
        interface_panel=workspace_bundle.get("interface_panel"),
        shell_state=selection.shell_state,
    )
    return build_portal_runtime_envelope(
        portal_scope=portal_scope.to_dict(),
        requested_surface_id=SYSTEM_ROOT_SURFACE_ID,
        surface_id=SYSTEM_ROOT_SURFACE_ID,
        entrypoint_id=PORTAL_SHELL_ENTRYPOINT_ID,
        read_write_posture="write",
        reducer_owned=True,
        canonical_route=selection.canonical_route,
        canonical_query=canonical_query_for_shell_state(selection.shell_state, surface_id=SYSTEM_ROOT_SURFACE_ID),
        canonical_url=selection.canonical_url,
        shell_state=selection.shell_state.to_dict(),
        surface_payload=workspace_bundle["surface_payload"],
        shell_composition=composition,
        warnings=[],
        error=preexisting_error,
    )


__all__ = [
    "PORTAL_RUNTIME_ENVELOPE_SCHEMA",
    "run_portal_shell_entry",
    "run_system_profile_basics_action",
]
