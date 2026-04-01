from __future__ import annotations

from typing import Any

from portal_core.shell.contracts import TOOL_CAPABILITY_SCHEMA, normalize_shell_verb


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        token = _text(item).lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


_TOOL_MEDIATION_SCOPE_TOKENS = {"tool_sandbox", "system_sandbox"}


def _is_tool_mediation_context(context: dict[str, Any], shell_verb: str) -> bool:
    return (
        _text(context.get("shell_surface")).lower() == "tool_mediation"
        and _text(context.get("mediation_scope")).lower() in _TOOL_MEDIATION_SCOPE_TOKENS
        and shell_verb == "mediate"
    )


def _normalize_supported_source_contracts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, str):
            out.append(
                {
                    "family_kind": "",
                    "family_types": [],
                    "scope_kinds": [],
                    "document_schema": item.strip(),
                    "row_file_keys": [],
                    "config_context": False,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "family_kind": _text(item.get("family_kind")).lower(),
                "family_types": _text_list(item.get("family_types") or item.get("family_type_tokens")),
                "scope_kinds": _text_list(item.get("scope_kinds")),
                "document_schema": _text(item.get("document_schema")),
                "row_file_keys": _text_list(item.get("row_file_keys")),
                "config_context": bool(item.get("config_context")),
            }
        )
    return out


def normalize_tool_capability(meta: dict[str, Any]) -> dict[str, Any]:
    raw = dict(meta or {})
    supported_verbs = _text_list(raw.get("supported_verbs"))
    if not supported_verbs:
        supported_verbs = ["mediate"]
    shell_composition_mode = "tool" if _text(raw.get("shell_composition_mode")).lower() == "tool" else "system"
    foreground_surface = _text(raw.get("foreground_surface")).lower()
    if foreground_surface not in {"interface_panel", "center_workbench"}:
        foreground_surface = "interface_panel" if shell_composition_mode == "tool" else "center_workbench"
    return {
        "schema": TOOL_CAPABILITY_SCHEMA,
        "tool_id": _text(raw.get("tool_id")),
        "label": _text(raw.get("display_name") or raw.get("label") or raw.get("title") or raw.get("tool_id")),
        "supported_verbs": [normalize_shell_verb(item) for item in supported_verbs if normalize_shell_verb(item)],
        "supported_source_contracts": _normalize_supported_source_contracts(raw.get("supported_source_contracts")),
        "config_context_support": bool(raw.get("config_context_support")),
        "source_resolution_rules": _text_list(raw.get("source_resolution_rules")),
        "workbench_contribution": _dict(raw.get("workbench_contribution")),
        "interface_panel_contribution": _dict(raw.get("interface_panel_contribution")),
        "inspector_card_contribution": _dict(raw.get("inspector_card_contribution")),
        "mutation_policy": _dict(raw.get("mutation_policy")),
        "preview_hooks": _dict(raw.get("preview_hooks")),
        "apply_hooks": _dict(raw.get("apply_hooks")),
        "mount_target": _text(raw.get("mount_target")),
        "home_path": _text(raw.get("home_path")),
        "route_prefix": _text(raw.get("route_prefix")),
        "icon": _text(raw.get("icon")),
        "surface_mode": _text(raw.get("surface_mode")) or "tool_shell",
        "owns_shell_state": bool(raw.get("owns_shell_state", True)),
        "shell_composition_mode": shell_composition_mode,
        "foreground_surface": foreground_surface,
        "service_contract": _dict(raw.get("service_contract")),
    }


def _match_source_contract(contract: dict[str, Any], context: dict[str, Any]) -> bool:
    schema = _text(context.get("schema"))
    if contract.get("config_context"):
        return schema == "mycite.shell.config_context.v1"
    if schema != "mycite.shell.selected_context.v1":
        return False
    document = _dict(context.get("document"))
    family = _dict(document.get("family"))
    scope = _dict(document.get("scope"))
    selection = _dict(context.get("selection"))
    family_kind = _text(family.get("kind")).lower()
    family_type = _text(family.get("type")).lower()
    family_subtype = _text(family.get("subtype")).lower()
    scope_kind = _text(scope.get("kind")).lower()
    row_file_key = _text(selection.get("row_file_key") or family_subtype).lower()
    document_schema = _text(document.get("schema"))

    expected_schema = _text(contract.get("document_schema"))
    if expected_schema and expected_schema != document_schema:
        return False
    expected_family_kind = _text(contract.get("family_kind"))
    if expected_family_kind and expected_family_kind != family_kind:
        return False
    family_types = _text_list(contract.get("family_types"))
    if family_types and family_type not in family_types and family_subtype not in family_types:
        return False
    scope_kinds = _text_list(contract.get("scope_kinds"))
    if scope_kinds and scope_kind not in scope_kinds:
        return False
    row_file_keys = _text_list(contract.get("row_file_keys"))
    if row_file_keys and row_file_key not in row_file_keys:
        return False
    return True


def tool_matches_context(meta: dict[str, Any], context: dict[str, Any]) -> bool:
    capability = normalize_tool_capability(meta)
    shell_verb = normalize_shell_verb(context.get("shell_verb"))
    if capability["supported_verbs"] and shell_verb not in capability["supported_verbs"]:
        return False
    if _text(context.get("schema")) == "mycite.shell.config_context.v1" and capability["config_context_support"]:
        return True
    if _is_tool_mediation_context(context, shell_verb) and capability["config_context_support"]:
        return True
    contracts = capability.get("supported_source_contracts") if isinstance(capability.get("supported_source_contracts"), list) else []
    if not contracts:
        return False
    return any(_match_source_contract(_dict(item), context) for item in contracts)


def compatible_tools_for_context(tool_tabs: list[dict[str, Any]] | None, context: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in list(tool_tabs or []):
        if not isinstance(raw, dict):
            continue
        capability = normalize_tool_capability(raw)
        if tool_matches_context(capability, context):
            out.append(capability)
    return out

