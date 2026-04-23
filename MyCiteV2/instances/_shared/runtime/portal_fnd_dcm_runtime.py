from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    FND_DCM_TOOL_REQUEST_SCHEMA,
    FND_DCM_TOOL_SURFACE_SCHEMA,
    PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
    PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    attach_region_family_contract,
    tool_exposure_configured,
    tool_exposure_enabled,
)
from MyCiteV2.packages.adapters.filesystem import FilesystemFndDcmReadOnlyAdapter
from MyCiteV2.packages.modules.cross_domain.fnd_dcm import FndDcmReadOnlyService
from MyCiteV2.packages.state_machine.portal_shell import (
    FND_DCM_DEFAULT_SITE,
    FND_DCM_TOOL_ENTRYPOINT_ID,
    FND_DCM_TOOL_ROUTE,
    FND_DCM_TOOL_SURFACE_ID,
    PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
    PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
    PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
    PORTAL_SHELL_REQUEST_SCHEMA,
    PortalScope,
    build_canonical_url,
    canonical_query_for_runtime_request_payload,
    resolve_portal_tool_registry_entry,
)
_ALLOWED_VIEWS = (
    ("overview", "Overview"),
    ("pages", "Pages"),
    ("collections", "Collections"),
    ("issues", "Issues"),
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _shell_state_payload(shell_state: object | None) -> dict[str, Any] | None:
    if isinstance(shell_state, dict):
        return dict(shell_state)
    to_dict = getattr(shell_state, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        return dict(payload) if isinstance(payload, dict) else None
    return None


def _shell_request(portal_scope: PortalScope, query: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema": PORTAL_SHELL_REQUEST_SCHEMA,
        "requested_surface_id": FND_DCM_TOOL_SURFACE_ID,
        "portal_scope": portal_scope.to_dict(),
        "surface_query": dict(query),
    }


def _href_for_query(query: Mapping[str, str]) -> str:
    return build_canonical_url(surface_id=FND_DCM_TOOL_SURFACE_ID, query=query)


def _normalize_surface_query(raw_query: Mapping[str, Any] | None) -> dict[str, str]:
    return canonical_query_for_runtime_request_payload(
        {"surface_query": raw_query},
        surface_id=FND_DCM_TOOL_SURFACE_ID,
    )


def _normalize_request(payload: dict[str, Any] | None) -> tuple[PortalScope, dict[str, str]]:
    normalized_payload = payload if isinstance(payload, dict) else {}
    schema = _as_text(normalized_payload.get("schema")) or FND_DCM_TOOL_REQUEST_SCHEMA
    if schema != FND_DCM_TOOL_REQUEST_SCHEMA:
        raise ValueError(f"request.schema must be {FND_DCM_TOOL_REQUEST_SCHEMA}")
    raw_scope = normalized_payload.get("portal_scope")
    portal_scope = PortalScope.from_value(raw_scope)
    if not portal_scope.capabilities:
        default_capabilities = ["datum_recognition", "spatial_projection"]
        if _as_text(portal_scope.scope_id).lower() == "fnd":
            default_capabilities.extend(["fnd_peripheral_routing", "hosted_site_manifest_visibility", "hosted_site_visibility"])
        portal_scope = PortalScope(scope_id=portal_scope.scope_id, capabilities=default_capabilities)
    return portal_scope, canonical_query_for_runtime_request_payload(
        normalized_payload,
        surface_id=FND_DCM_TOOL_SURFACE_ID,
        legacy_query_keys=("site", "view", "page", "collection"),
    )


def _tool_status(
    *,
    portal_scope: PortalScope,
    tool_exposure_policy: dict[str, Any] | None,
    webapps_root: str | Path | None,
) -> dict[str, Any]:
    tool_entry = resolve_portal_tool_registry_entry(surface_id=FND_DCM_TOOL_SURFACE_ID)
    if tool_entry is None:
        raise ValueError("FND-DCM tool surface is not registered")
    configured = tool_exposure_configured(tool_exposure_policy, tool_id=tool_entry.tool_id)
    enabled = tool_exposure_enabled(tool_exposure_policy, tool_id=tool_entry.tool_id)
    webapps_path = Path(webapps_root) if webapps_root is not None else None
    missing_integrations = []
    if webapps_path is None or not webapps_path.exists() or not webapps_path.is_dir():
        missing_integrations.append("webapps_root")
    missing_capabilities = [
        capability for capability in tool_entry.required_capabilities if capability not in portal_scope.capabilities
    ]
    return {
        "tool_id": tool_entry.tool_id,
        "label": tool_entry.label,
        "summary": tool_entry.summary,
        "configured": configured,
        "enabled": enabled,
        "operational": bool(configured and enabled and not missing_integrations and not missing_capabilities),
        "missing_integrations": missing_integrations,
        "required_capabilities": list(tool_entry.required_capabilities),
        "missing_capabilities": missing_capabilities,
    }


def _facts_rows(items: list[tuple[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for label, value in items:
        token = _as_text(value)
        rows.append({"label": label, "value": token or "—"})
    return rows


def _build_control_panel(
    *,
    portal_scope: PortalScope,
    workspace: dict[str, Any],
) -> dict[str, Any]:
    canonical_query = _as_dict(workspace.get("canonical_query"))
    selected_site = _as_text(workspace.get("selected_site"))
    selected_label = _as_text(workspace.get("selected_label")) or selected_site
    selected_view = _as_text(workspace.get("view")) or "overview"
    groups = [
        {
            "title": "Sites",
            "entries": [
                {
                    "label": _as_text(row.get("label")) or _as_text(row.get("domain")),
                    "meta": " · ".join(
                        [
                            token
                            for token in (
                                _as_text(row.get("schema")),
                                f"{int(row.get('page_count') or 0)} pages",
                                f"{int(row.get('collection_count') or 0)} collections",
                                (
                                    f"{int(row.get('issue_count') or 0)} issues"
                                    if int(row.get("issue_count") or 0)
                                    else ""
                                ),
                            )
                            if token
                        ]
                    ),
                    "active": bool(row.get("selected")),
                    "href": _href_for_query(
                        {
                            "site": _as_text(row.get("domain")) or FND_DCM_DEFAULT_SITE,
                            "view": "overview",
                        }
                    ),
                    "shell_request": _shell_request(
                        portal_scope,
                        {
                            "site": _as_text(row.get("domain")) or FND_DCM_DEFAULT_SITE,
                            "view": "overview",
                        },
                    ),
                }
                for row in _as_list(workspace.get("site_cards"))
            ],
        },
        {
            "title": "Views",
            "entries": [
                {
                    "label": label,
                    "active": view_id == selected_view,
                    "href": _href_for_query(
                        {
                            "site": selected_site or FND_DCM_DEFAULT_SITE,
                            "view": view_id,
                        }
                    ),
                    "shell_request": _shell_request(
                        portal_scope,
                        {
                            "site": selected_site or FND_DCM_DEFAULT_SITE,
                            "view": view_id,
                        },
                    ),
                }
                for view_id, label in _ALLOWED_VIEWS
            ],
        },
    ]
    if selected_view == "pages":
        groups.append(
            {
                "title": "Pages",
                "entries": [
                    {
                        "label": _as_text(row.get("title")) or _as_text(row.get("id")),
                        "meta": _as_text(row.get("template")),
                        "active": _as_text(row.get("id")) == _as_text(workspace.get("page")),
                        "href": _href_for_query(
                            {
                                "site": selected_site or FND_DCM_DEFAULT_SITE,
                                "view": "pages",
                                "page": _as_text(row.get("id")),
                            }
                        ),
                        "shell_request": _shell_request(
                            portal_scope,
                            {
                                "site": selected_site or FND_DCM_DEFAULT_SITE,
                                "view": "pages",
                                "page": _as_text(row.get("id")),
                            },
                        ),
                    }
                    for row in _as_list(workspace.get("pages"))
                ],
            }
        )
    if selected_view == "collections":
        groups.append(
            {
                "title": "Collections",
                "entries": [
                    {
                        "label": _as_text(row.get("id")),
                        "meta": " · ".join(
                            [token for token in (_as_text(row.get("type")), f"{int(row.get('source_count') or 0)} source files") if token]
                        ),
                        "active": _as_text(row.get("id")) == _as_text(workspace.get("collection")),
                        "href": _href_for_query(
                            {
                                "site": selected_site or FND_DCM_DEFAULT_SITE,
                                "view": "collections",
                                "collection": _as_text(row.get("id")),
                            }
                        ),
                        "shell_request": _shell_request(
                            portal_scope,
                            {
                                "site": selected_site or FND_DCM_DEFAULT_SITE,
                                "view": "collections",
                                "collection": _as_text(row.get("id")),
                            },
                        ),
                    }
                    for row in _as_list(workspace.get("collections"))
                ],
            }
        )
    context_items = [
        {"label": "Sandbox", "value": "FND-DCM"},
        {"label": "Site", "value": selected_label or "—"},
        {"label": "View", "value": selected_view.title()},
    ]
    if selected_view == "pages":
        context_items.append({"label": "Page", "value": _as_text(workspace.get("page")) or "—"})
    if selected_view == "collections":
        context_items.append({"label": "Collection", "value": _as_text(workspace.get("collection")) or "—"})
    return {
        "schema": PORTAL_SHELL_REGION_CONTROL_PANEL_SCHEMA,
        "kind": "focus_selection_panel",
        "title": "Control Panel",
        "surface_label": "FND-DCM",
        "context_items": context_items,
        "verb_tabs": [],
        "groups": groups,
        "actions": [],
    }


def _build_inspector(
    *,
    tool_status: dict[str, Any],
    workspace: dict[str, Any],
) -> dict[str, Any]:
    overview = _as_dict(workspace.get("overview"))
    selected_page = _as_dict(workspace.get("selected_page"))
    selected_collection = _as_dict(workspace.get("selected_collection"))
    subject = None
    if selected_page:
        subject = {"level": "page", "id": _as_text(selected_page.get("id"))}
    elif selected_collection:
        subject = {"level": "collection", "id": _as_text(selected_collection.get("id"))}
    sections = [
        {
            "title": "Tool Posture",
            "rows": _facts_rows(
                [
                    ("configured", "yes" if tool_status.get("configured") else "no"),
                    ("enabled", "yes" if tool_status.get("enabled") else "no"),
                    ("operational", "yes" if tool_status.get("operational") else "no"),
                    ("required capabilities", ", ".join(_as_list(tool_status.get("required_capabilities")))),
                    ("missing capabilities", ", ".join(_as_list(tool_status.get("missing_capabilities")))),
                    ("missing integrations", ", ".join(_as_list(tool_status.get("missing_integrations")))),
                ]
            ),
        },
        {
            "title": "Selection",
            "rows": _facts_rows(
                [
                    ("site", overview.get("domain")),
                    ("label", overview.get("label")),
                    ("view", workspace.get("view")),
                    ("manifest schema", overview.get("manifest_schema")),
                ]
            ),
        },
        {
            "title": "Overview",
            "rows": _facts_rows(
                [
                    ("site name", overview.get("site_name")),
                    ("homepage", overview.get("homepage_href")),
                    ("manifest", overview.get("manifest_path")),
                    ("render script", overview.get("render_script_path")),
                    ("pages", overview.get("page_count")),
                    ("collections", overview.get("collection_count")),
                    ("issues", overview.get("issue_count")),
                ]
            ),
        },
    ]
    if selected_page:
        sections.append(
            {
                "title": "Selected Page",
                "rows": _facts_rows(
                    [
                        ("page id", selected_page.get("id")),
                        ("file", selected_page.get("file")),
                        ("template", selected_page.get("template")),
                        ("collections", ", ".join(_as_list(selected_page.get("collection_refs")))),
                    ]
                ),
            }
        )
    if selected_collection:
        sections.append(
            {
                "title": "Selected Collection",
                "rows": _facts_rows(
                    [
                        ("collection id", selected_collection.get("id")),
                        ("type", selected_collection.get("type")),
                        ("source count", selected_collection.get("source_count")),
                    ]
                ),
            }
        )
    if _as_list(workspace.get("issues")):
        sections.append(
            {
                "title": "Issues",
                "rows": [
                    {
                        "label": _as_text(item.get("code")) or "issue",
                        "value": _as_text(item.get("severity")) or "warning",
                        "detail": _as_text(item.get("message")),
                    }
                    for item in _as_list(workspace.get("issues"))[:8]
                    if isinstance(item, dict)
                ],
            }
        )
    return {
        "schema": PORTAL_SHELL_REGION_INSPECTOR_SCHEMA,
        "kind": "summary_panel",
        "title": "FND-DCM",
        "summary": "Hosted manifest inspection and collection normalization.",
        "subject": subject,
        "sections": sections,
    }


def _workbench_surface_payload(workspace: dict[str, Any]) -> dict[str, Any]:
    board_profile_preview = _as_dict(workspace.get("board_profile_preview"))
    notes = [
        "FND-DCM is read-only in v1.",
        "Workbench evidence stays hidden until explicitly opened.",
    ]
    if board_profile_preview:
        notes.append(
            f"Board profile normalization preview found {int(board_profile_preview.get('count') or 0)} profiles and {int(board_profile_preview.get('summary_count') or 0)} summaries."
        )
    return {
        "kind": "fnd_dcm_secondary_evidence",
        "title": "FND-DCM Evidence",
        "cards": [
            {"label": "Site", "value": _as_text(workspace.get("selected_label")) or _as_text(workspace.get("selected_site"))},
            {"label": "View", "value": _as_text(workspace.get("view")) or "overview"},
            {"label": "Sources", "value": str(len(_as_list(workspace.get("selected_collection_sources"))))},
            {"label": "Issues", "value": str(len(_as_list(workspace.get("issues"))))},
        ],
        "sections": [
            {
                "title": "Manifest JSON",
                "summary": _as_text(_as_dict(workspace.get("tool_files")).get("manifest_path")),
                "preformatted": _as_text(workspace.get("raw_manifest_json")),
            },
            {
                "title": "Collection Sources",
                "columns": [
                    {"key": "collection_id", "label": "Collection"},
                    {"key": "source_kind", "label": "Kind"},
                    {"key": "relative_path", "label": "Relative Path"},
                    {"key": "exists", "label": "Exists"},
                ],
                "items": [
                    {
                        "collection_id": _as_text(item.get("collection_id")),
                        "source_kind": _as_text(item.get("source_kind")),
                        "relative_path": _as_text(item.get("relative_path")),
                        "exists": "yes" if item.get("exists") else "no",
                    }
                    for item in _as_list(workspace.get("selected_collection_sources"))
                    if isinstance(item, dict)
                ],
            },
            {
                "title": "Normalization Evidence",
                "rows": [
                    {"label": "step", "value": _as_text(item)}
                    for item in _as_list(workspace.get("normalization_evidence"))
                    if _as_text(item)
                ],
            },
        ],
        "notes": notes,
    }


def _surface_payload(
    *,
    workspace: dict[str, Any],
    tool_status: dict[str, Any],
) -> dict[str, Any]:
    overview = _as_dict(workspace.get("overview"))
    return {
        "schema": FND_DCM_TOOL_SURFACE_SCHEMA,
        "kind": "tool_mediation_surface",
        "tool_id": "fnd_dcm",
        "surface_id": FND_DCM_TOOL_SURFACE_ID,
        "entrypoint_id": FND_DCM_TOOL_ENTRYPOINT_ID,
        "title": "FND-DCM",
        "subtitle": "Hosted manifest inspection and collection normalization.",
        "tool": tool_status,
        "request_contract": {
            "schema": FND_DCM_TOOL_REQUEST_SCHEMA,
            "route": FND_DCM_TOOL_ROUTE,
            "surface_id": FND_DCM_TOOL_SURFACE_ID,
        },
        "cards": [
            {"label": "Site", "value": _as_text(workspace.get("selected_label")) or _as_text(workspace.get("selected_site"))},
            {"label": "Pages", "value": str(int(overview.get("page_count") or 0))},
            {"label": "Collections", "value": str(int(overview.get("collection_count") or 0))},
            {"label": "Operational", "value": "yes" if tool_status.get("operational") else "no"},
        ],
        "notes": [
            "FND-DCM is one service tool surface under SYSTEM.",
            "The shared read model keeps site-specific frontend behavior in extensions instead of forcing one renderer.",
        ],
        "workspace": workspace,
    }


def build_portal_fnd_dcm_surface_bundle(
    *,
    portal_scope: PortalScope,
    shell_state: object | None,
    surface_query: Mapping[str, Any] | None,
    webapps_root: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_status = _tool_status(
        portal_scope=portal_scope,
        tool_exposure_policy=tool_exposure_policy,
        webapps_root=webapps_root,
    )
    query = _normalize_surface_query(surface_query)
    service = FndDcmReadOnlyService(
        FilesystemFndDcmReadOnlyAdapter(
            private_dir,
            webapps_root=webapps_root,
        )
    )
    workspace = service.read_surface(
        portal_tenant_id=portal_scope.scope_id,
        site=query.get("site") or FND_DCM_DEFAULT_SITE,
        view=query.get("view") or "overview",
        page=query.get("page") or "",
        collection=query.get("collection") or "",
    )
    canonical_query = _as_dict(workspace.get("canonical_query"))
    surface_payload = _surface_payload(workspace=workspace, tool_status=tool_status)
    return {
        "entrypoint_id": FND_DCM_TOOL_ENTRYPOINT_ID,
        "read_write_posture": "read-only",
        "page_title": "FND-DCM",
        "page_subtitle": "Read-only hosted manifest inspection and normalization.",
        "surface_payload": surface_payload,
        "control_panel": attach_region_family_contract(
            _build_control_panel(portal_scope=portal_scope, workspace=workspace),
            family=PORTAL_REGION_FAMILY_DIRECTIVE_PANEL,
            surface_id=FND_DCM_TOOL_SURFACE_ID,
        ),
        "workbench": attach_region_family_contract(
            {
                "schema": PORTAL_SHELL_REGION_WORKBENCH_SCHEMA,
                "kind": "fnd_dcm_workbench",
                "title": "FND-DCM Evidence",
                "subtitle": "Raw manifest JSON, collection file metadata, and normalization evidence.",
                "visible": False,
                "surface_payload": _workbench_surface_payload(workspace),
            },
            family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
            surface_id=FND_DCM_TOOL_SURFACE_ID,
        ),
        "inspector": attach_region_family_contract(
            _build_inspector(tool_status=tool_status, workspace=workspace),
            family=PORTAL_REGION_FAMILY_PRESENTATION_SURFACE,
            surface_id=FND_DCM_TOOL_SURFACE_ID,
        ),
        "canonical_route": FND_DCM_TOOL_ROUTE,
        "canonical_query": canonical_query,
        "canonical_url": build_canonical_url(surface_id=FND_DCM_TOOL_SURFACE_ID, query=canonical_query),
        "shell_state": _shell_state_payload(shell_state),
    }


def run_portal_fnd_dcm(
    request_payload: dict[str, Any] | None,
    *,
    webapps_root: str | Path | None,
    private_dir: str | Path | None = None,
    tool_exposure_policy: dict[str, Any] | None = None,
    portal_instance_id: str | None = None,
    portal_domain: str = "",
) -> dict[str, Any]:
    portal_scope, surface_query = _normalize_request(request_payload)
    resolved_portal_instance_id = _as_text(portal_instance_id) or portal_scope.scope_id
    if not portal_scope.scope_id:
        portal_scope = PortalScope(scope_id=resolved_portal_instance_id, capabilities=portal_scope.capabilities)
    shell_request = {
        "schema": PORTAL_SHELL_REQUEST_SCHEMA,
        "requested_surface_id": FND_DCM_TOOL_SURFACE_ID,
        "portal_scope": portal_scope.to_dict(),
        "surface_query": surface_query,
    }
    from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry

    return run_portal_shell_entry(
        shell_request,
        portal_instance_id=resolved_portal_instance_id,
        portal_domain=portal_domain,
        webapps_root=webapps_root,
        private_dir=private_dir,
        tool_exposure_policy=tool_exposure_policy,
    )


__all__ = [
    "build_portal_fnd_dcm_surface_bundle",
    "run_portal_fnd_dcm",
]
