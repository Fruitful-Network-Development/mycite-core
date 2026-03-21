from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from _shared.portal.application.shell.contracts import CONFIG_CONTEXT_SCHEMA, build_inspector_card
from _shared.portal.application.shell.tools import compatible_tools_for_context
from _shared.portal.data_engine.profile_config_refs import get_path, set_path


AGRO_CONFIG_BINDINGS_SCHEMA = "mycite.agro_erp.config_bindings.v1"
_RESOURCE_ROLE_PATH = "agro.bindings.resource_roles"
_LEGACY_PRODUCT_REF_PATH = "agro.inherited.product_profile_ref"
_LEGACY_SUPPLY_LOG_REF_PATH = "agro.inherited.supply_log_ref"
_ROLE_ORDER = ("txa", "msn", "erp")


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _instance_payload(portal_instance_context: Any | None) -> dict[str, Any]:
    if portal_instance_context is None:
        return {}
    if is_dataclass(portal_instance_context):
        payload = asdict(portal_instance_context)
        return {str(key): str(value) for key, value in payload.items()}
    if isinstance(portal_instance_context, dict):
        return {str(key): str(value) for key, value in portal_instance_context.items()}
    return {}


def _expected_tokens_for_role(role: str) -> list[str]:
    token = _text(role).lower()
    if token == "txa":
        return ["txa", "taxonomy"]
    if token == "msn":
        return ["msn", "identity"]
    if token == "erp":
        return ["erp", "resource"]
    return [token]


def _candidate_payload(document: dict[str, Any]) -> dict[str, Any]:
    identity = _dict(document.get("identity"))
    family = _dict(document.get("family"))
    scope = _dict(document.get("scope"))
    provenance = _dict(document.get("provenance"))
    logical_key = _text(identity.get("logical_key"))
    source_msn_id = _text(provenance.get("source_msn_id"))
    source_scope = _text(scope.get("kind"))
    if source_scope == "inherited" and source_msn_id and logical_key:
        activation_payload = {"source_msn_id": source_msn_id, "resource_id": logical_key}
    else:
        activation_payload = {"local_resource_id": logical_key}
    return {
        "document_id": _text(identity.get("document_id")),
        "logical_key": logical_key,
        "display_name": _text(identity.get("display_name") or logical_key),
        "family_kind": _text(family.get("kind")),
        "family_type": _text(family.get("type")),
        "scope_kind": source_scope,
        "provenance": provenance,
        "activation_payload": activation_payload,
    }


def _validate_document_for_role(role: str, document: dict[str, Any]) -> bool:
    candidate = _candidate_payload(document)
    haystacks = [
        _text(candidate.get("logical_key")).lower(),
        _text(candidate.get("display_name")).lower(),
        _text(candidate.get("family_type")).lower(),
        _text(candidate.get("scope_kind")).lower(),
    ]
    tokens = _expected_tokens_for_role(role)
    return any(token in text for token in tokens for text in haystacks if text)


def _all_candidates(
    *,
    local_documents: list[dict[str, Any]],
    inherited_documents: list[dict[str, Any]],
    sandbox_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for source in (inherited_documents, local_documents, sandbox_documents):
        for item in list(source or []):
            if isinstance(item, dict):
                documents.append(item)
    return documents


def _explicit_role_binding(config: dict[str, Any], role: str) -> dict[str, Any]:
    store = _dict(get_path(config, _RESOURCE_ROLE_PATH))
    raw = store.get(role)
    if isinstance(raw, str):
        return {"resource_id": raw}
    return _dict(raw)


def _resolve_role_binding(
    *,
    role: str,
    explicit: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    preferred_scope = "inherited" if role in {"txa", "msn"} else ""
    allow_auto_discovery = explicit.get("allow_auto_discovery", True) is not False
    explicit_scope = _text(explicit.get("scope")).lower()
    explicit_resource_id = _text(explicit.get("resource_id") or explicit.get("logical_key")).lower()
    explicit_document_id = _text(explicit.get("document_id")).lower()

    valid_candidates = [item for item in candidates if _validate_document_for_role(role, item)]

    def _candidate_rank(document: dict[str, Any]) -> tuple[int, int, str]:
        candidate = _candidate_payload(document)
        scope_kind = _text(candidate.get("scope_kind")).lower()
        if scope_kind == preferred_scope:
            scope_rank = 0
        elif scope_kind == "sandbox":
            scope_rank = 1
        elif scope_kind == "local":
            scope_rank = 2
        else:
            scope_rank = 3
        logical_key = _text(candidate.get("logical_key")).lower()
        family_type = _text(candidate.get("family_type")).lower()
        return scope_rank, 0 if role in logical_key or role in family_type else 1, logical_key

    resolved: dict[str, Any] = {}
    warnings: list[str] = []
    resolution_mode = "unresolved"
    if explicit:
        for document in valid_candidates:
            candidate = _candidate_payload(document)
            if explicit_document_id and _text(candidate.get("document_id")).lower() == explicit_document_id:
                resolved = candidate
                resolution_mode = "explicit"
                break
            if explicit_resource_id and _text(candidate.get("logical_key")).lower() == explicit_resource_id:
                resolved = candidate
                resolution_mode = "explicit"
                break
            if explicit_scope and explicit_resource_id and _text(candidate.get("scope_kind")).lower() == explicit_scope and _text(candidate.get("logical_key")).lower() == explicit_resource_id:
                resolved = candidate
                resolution_mode = "explicit"
                break
        if not resolved:
            warnings.append(f"Explicit {role} binding is configured but no matching resource was found.")
    if not resolved and allow_auto_discovery and valid_candidates:
        ranked = sorted(valid_candidates, key=_candidate_rank)
        resolved = _candidate_payload(ranked[0])
        resolution_mode = "auto"
        if preferred_scope and _text(resolved.get("scope_kind")) != preferred_scope:
            warnings.append(f"{role} binding fell back to {_text(resolved.get('scope_kind')) or 'unknown'} scope because no inherited resource was available.")

    return {
        "role": role,
        "preferred_scope": preferred_scope or "local",
        "resolution_mode": resolution_mode,
        "explicit_binding": explicit,
        "allow_auto_discovery": allow_auto_discovery,
        "resolved": resolved,
        "valid": bool(resolved),
        "warnings": warnings,
        "candidates": [_candidate_payload(item) for item in sorted(valid_candidates, key=_candidate_rank)],
    }


def build_agro_config_context(
    *,
    active_config: dict[str, Any],
    tool_tabs: list[dict[str, Any]] | None,
    local_documents: list[dict[str, Any]],
    inherited_documents: list[dict[str, Any]],
    sandbox_documents: list[dict[str, Any]],
    portal_instance_context: Any | None = None,
    portal_instance_id: str = "",
    msn_id: str = "",
) -> dict[str, Any]:
    candidates = _all_candidates(
        local_documents=local_documents,
        inherited_documents=inherited_documents,
        sandbox_documents=sandbox_documents,
    )
    role_bindings = {
        role: _resolve_role_binding(
            role=role,
            explicit=_explicit_role_binding(active_config, role),
            candidates=candidates,
        )
        for role in _ROLE_ORDER
    }
    property_payload = _dict(active_config.get("property"))
    config_context = {
        "ok": True,
        "schema": CONFIG_CONTEXT_SCHEMA,
        "bindings_schema": AGRO_CONFIG_BINDINGS_SCHEMA,
        "tool_id": "agro_erp",
        "shell_verb": "mediate",
        "portal_instance_id": _text(portal_instance_id),
        "msn_id": _text(msn_id),
        "portal_instance_context": _instance_payload(portal_instance_context),
        "binding_truth": "config",
        "browse_truth": "inherited_resources",
        "staging_truth": "sandbox_reduced",
        "commit_truth": "anthology_semantic_minimum",
        "property_refs": {
            "title": _text(property_payload.get("title")),
            "bbox_refs": list(property_payload.get("bbox") or []),
            "geometry_type": _text(_dict(property_payload.get("geometry")).get("type")),
            "geometry_refs": list(_dict(property_payload.get("geometry")).get("coordinates") or []),
        },
        "resource_role_bindings": role_bindings,
        "sandbox_targets": {
            "product_profile": "sandbox:agro_erp.product_profile",
            "supply_log": "sandbox:agro_erp.supply_log",
            "tool_session_open": "/portal/api/data/sandbox/tool_session/open",
        },
        "anthology_commit_targets": {
            "product_profile_ref_path": _LEGACY_PRODUCT_REF_PATH,
            "supply_log_ref_path": _LEGACY_SUPPLY_LOG_REF_PATH,
            "product_profile_ref": _text(get_path(active_config, _LEGACY_PRODUCT_REF_PATH)),
            "supply_log_ref": _text(get_path(active_config, _LEGACY_SUPPLY_LOG_REF_PATH)),
        },
        "activation": {
            "tool_id": "agro_erp",
            "default_verb": "mediate",
            "can_open": bool(_dict(role_bindings.get("txa")).get("resolved")),
            "request_payload": _dict(_dict(role_bindings.get("txa")).get("resolved")).get("activation_payload") or {},
        },
    }
    config_context["compatible_tools"] = compatible_tools_for_context(tool_tabs, config_context)
    config_context["inspector_cards"] = [
        build_inspector_card(
            card_id="agro-bindings",
            title="AGRO ERP Bindings",
            summary="Config is binding truth",
            body={"resource_role_bindings": role_bindings},
            kind="mediation",
        ),
        build_inspector_card(
            card_id="agro-commit-policy",
            title="Staging + Commit Policy",
            summary="Reduced sandbox staging, minimal anthology commits",
            body={
                "binding_truth": config_context["binding_truth"],
                "browse_truth": config_context["browse_truth"],
                "staging_truth": config_context["staging_truth"],
                "commit_truth": config_context["commit_truth"],
                "anthology_commit_targets": config_context["anthology_commit_targets"],
            },
            kind="policy",
        ),
    ]
    return config_context


def update_agro_config_bindings(
    active_config: dict[str, Any],
    *,
    resource_roles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_payload = dict(active_config if isinstance(active_config, dict) else {})
    if isinstance(resource_roles, dict):
        for role in _ROLE_ORDER:
            raw = resource_roles.get(role)
            if raw is None:
                continue
            binding = _dict(raw)
            binding.setdefault("allow_auto_discovery", True)
            next_payload = set_path(next_payload, f"{_RESOURCE_ROLE_PATH}.{role}", binding)
    return next_payload
