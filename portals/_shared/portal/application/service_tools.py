from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _shared.portal.application.shell.contracts import CONFIG_CONTEXT_SCHEMA, build_inspector_card
from _shared.portal.application.shell.tools import compatible_tools_for_context
from _shared.portal.runtime_paths import utility_tools_dir


SERVICE_TOOL_CONTRACT_SCHEMA = "mycite.service_tool.contract.v1"
SERVICE_TOOL_BINDINGS_SCHEMA = "mycite.service_tool.config_bindings.v1"

_SERVICE_TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "fnd_ebi": {
        "namespace": "fnd-ebi",
        "workspace_id": "service.fnd_ebi",
        "label": "Analytics profile cards",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["fnd-ebi.{portal_instance_id}.json", "fnd-ebi.*.json"],
        "collection_patterns": ["web-analytics.json"],
        "member_patterns": ["web-analytics.json", "fnd-ebi.*.json", "*.ndjson"],
    },
    "aws_platform_admin": {
        "namespace": "aws-csm",
        "workspace_id": "service.aws_platform_admin",
        "label": "AWS service profiles",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["aws-csm.{portal_instance_id}.json", "aws-csm.*.json"],
        "collection_patterns": ["aws-csm.collection.json"],
        "member_patterns": ["aws-csm.collection.json", "aws-csm.*.json", "*.ndjson"],
    },
    "aws_tenant_actions": {
        "namespace": "aws-csm",
        "workspace_id": "service.aws_tenant_actions",
        "label": "AWS service profiles",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["aws-csm.{portal_instance_id}.json", "aws-csm.*.json"],
        "collection_patterns": ["aws-csm.collection.json"],
        "member_patterns": ["aws-csm.collection.json", "aws-csm.*.json", "*.ndjson"],
    },
    "paypal_service_agreement": {
        "namespace": "paypal-csm",
        "workspace_id": "service.paypal_service_agreement",
        "label": "PayPal service profiles",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json"],
        "collection_patterns": ["paypal-csm.collection.json"],
        "member_patterns": ["paypal-csm.collection.json", "{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json", "*.ndjson"],
    },
    "paypal_tenant_actions": {
        "namespace": "paypal-csm",
        "workspace_id": "service.paypal_tenant_actions",
        "label": "PayPal service profiles",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json"],
        "collection_patterns": ["paypal-csm.collection.json"],
        "member_patterns": ["paypal-csm.collection.json", "{portal_instance_id}.json", "paypal-csm.{portal_instance_id}.json", "*.ndjson"],
    },
    "operations": {
        "namespace": "keycloak-sso",
        "workspace_id": "service.operations",
        "label": "Portal operations cards",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["keycloak-sso.{portal_instance_id}.json", "keycloak-sso.*.json"],
        "collection_patterns": ["portal_instances.json"],
        "member_patterns": ["portal_instances.json", "keycloak-sso.*.json", "*.ndjson"],
    },
    "fnd_provisioning": {
        "namespace": "keycloak-sso",
        "workspace_id": "service.fnd_provisioning",
        "label": "Portal operations cards",
        "default_mode": "profiles",
        "modes": ["profiles", "collections", "files"],
        "config_patterns": ["keycloak-sso.{portal_instance_id}.json", "keycloak-sso.*.json"],
        "collection_patterns": ["portal_instances.json"],
        "member_patterns": ["portal_instances.json", "keycloak-sso.*.json", "*.ndjson"],
    },
}


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _instance_payload(portal_instance_context: Any | None) -> dict[str, Any]:
    if isinstance(portal_instance_context, dict):
        return {str(key): str(value) for key, value in portal_instance_context.items()}
    return {}


def service_tool_definition(tool_id: str) -> dict[str, Any]:
    return dict(_SERVICE_TOOL_DEFINITIONS.get(_text(tool_id).lower()) or {})


def _expand_patterns(values: Any, *, portal_instance_id: str = "") -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        token = _text(item)
        if not token:
            continue
        try:
            token = token.format(portal_instance_id=_text(portal_instance_id))
        except Exception:
            pass
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _service_tool_contract(definition: dict[str, Any], *, portal_instance_id: str = "") -> dict[str, Any]:
    return {
        "schema": SERVICE_TOOL_CONTRACT_SCHEMA,
        "tool_namespace": _text(definition.get("namespace")),
        "mediation_host_path": "/portal/system",
        "config_datum": {
            "patterns": _expand_patterns(definition.get("config_patterns"), portal_instance_id=portal_instance_id),
            "content_kind": "json",
        },
        "collection_datum": {
            "patterns": _expand_patterns(definition.get("collection_patterns"), portal_instance_id=portal_instance_id),
            "content_kind": "json_collection",
        },
        "profile_card_contract": {
            "card_kind": "service_profile",
            "source": "tool_owned_datums",
        },
        "collection_view_contract": {
            "default_mode": _text(definition.get("default_mode")) or "profiles",
            "modes": list(definition.get("modes") or []),
        },
    }


def build_service_tool_meta(tool_id: str) -> dict[str, Any]:
    definition = service_tool_definition(tool_id)
    if not definition:
        return {}
    return {
        "supported_verbs": ["mediate"],
        "supported_source_contracts": [{"config_context": True}],
        "config_context_support": True,
        "source_resolution_rules": ["tool_json_collection", "profile_card_mediation"],
        "workbench_contribution": {
            "workspace_id": _text(definition.get("workspace_id")),
            "label": _text(definition.get("label")),
            "default_mode": _text(definition.get("default_mode")) or "overview",
            "modes": list(definition.get("modes") or []),
        },
        "inspector_card_contribution": {
            "config_context_route": f"/portal/api/data/system/config_context/{_text(tool_id).lower()}",
        },
        "mutation_policy": {
            "binding_truth": "tool_state_files",
            "browse_truth": "tool_json_collection",
            "sandbox_truth": "tool_scoped_manual_edits",
            "anthology_truth": "none",
        },
        "preview_hooks": {},
        "apply_hooks": {},
        "surface_mode": "mediation_only",
        "owns_shell_state": False,
        "service_contract": _service_tool_contract(definition),
    }


def _tool_root(private_dir: Path, namespace: str) -> Path:
    return utility_tools_dir(private_dir) / namespace


def _iter_collection_files(root: Path, patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            out.append(path)
    return out


def _load_json_or_lines(path: Path) -> tuple[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".ndjson":
        rows: list[Any] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                rows.append({"raw": line})
        return "ndjson", rows
    try:
        return "json", json.loads(text)
    except Exception:
        return "text", text


def _describe_file(root: Path, path: Path | None) -> tuple[dict[str, Any], Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}, {}
    kind, payload = _load_json_or_lines(path)
    record_count = len(payload) if isinstance(payload, list) else len(payload) if isinstance(payload, dict) else 1
    return (
        {
            "file_name": path.name,
            "relative_path": path.relative_to(root).as_posix(),
            "path": str(path),
            "content_kind": kind,
            "record_count": int(record_count),
            "schema": _text(payload.get("schema")) if isinstance(payload, dict) else "",
            "summary": _json_summary(payload),
        },
        payload,
    )


def _pick_canonical_file(root: Path, patterns: list[str]) -> Path | None:
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                return path
    return None


def _member_files_from_collection_payload(root: Path, payload: Any) -> list[Path]:
    if not isinstance(payload, dict):
        return []
    out: list[Path] = []
    seen: set[Path] = set()
    token_seen: set[str] = set()

    def _collect_token(raw: Any) -> str:
        token = _text(raw)
        lower = token.lower()
        if not token or not (lower.endswith(".json") or lower.endswith(".ndjson")):
            return ""
        if token in token_seen:
            return ""
        token_seen.add(token)
        return token

    tokens: list[str] = []
    for item in list(payload.get("member_files") or []):
        token = _collect_token(item)
        if token:
            tokens.append(token)

    # Backward-compatible parse for tuple/list encoded collection rows (e.g. web-analytics.json).
    for value in payload.values():
        if isinstance(value, str):
            token = _collect_token(value)
            if token:
                tokens.append(token)
            continue
        if not isinstance(value, list):
            continue
        for node in value:
            if isinstance(node, str):
                token = _collect_token(node)
                if token:
                    tokens.append(token)
                continue
            if not isinstance(node, list):
                continue
            for item in node:
                token = _collect_token(item)
                if token:
                    tokens.append(token)

    def _resolve_member_path(token: str) -> Path | None:
        base = (root / token).resolve()
        candidates = [base]
        lower = token.lower()
        if lower.endswith(".ndjson"):
            candidates.append((root / (token[:-7] + ".json")).resolve())
        elif lower.endswith(".json"):
            candidates.append((root / (token[:-5] + ".ndjson")).resolve())
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    for token in tokens:
        path = _resolve_member_path(token)
        if path is None or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def build_service_tool_registration(tool_id: str, display_name: str) -> dict[str, object]:
    return {
        "tool_id": _text(tool_id).lower(),
        "display_name": _text(display_name) or _text(tool_id).replace("_", " ").title(),
        "route_prefix": "",
        "home_path": "",
        "surface_mode": "mediation_only",
        "owns_shell_state": False,
        **build_service_tool_meta(tool_id),
    }


def _json_summary(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        keys = sorted(str(key) for key in payload.keys())
        return {"kind": "object", "key_count": len(keys), "keys": keys[:12]}
    if isinstance(payload, list):
        return {"kind": "list", "item_count": len(payload), "sample": payload[:3]}
    return {"kind": "scalar", "value": payload}


def _profile_cards_for_payload(path: Path, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    if path.name == "portal_instances.json":
        cards: list[dict[str, Any]] = []
        instances = payload.get("instances") if isinstance(payload.get("instances"), dict) else {}
        for portal_id, instance_payload in sorted(instances.items()):
            if not isinstance(instance_payload, dict):
                continue
            cards.append(
                {
                    "card_id": f"{path.stem}:{portal_id}",
                    "title": portal_id,
                    "summary": _text(instance_payload.get("mode") or "unknown"),
                    "body": {
                        "auth_mode": _text(instance_payload.get("auth_mode")),
                        "mode": _text(instance_payload.get("mode")),
                        "updated_at_unix_ms": int(instance_payload.get("updated_at_unix_ms") or 0),
                    },
                }
            )
        return cards

    title = (
        _text(payload.get("title"))
        or _text(payload.get("domain"))
        or _text(payload.get("service_agreement_id"))
        or path.stem
    )
    summary = (
        _text(payload.get("schema"))
        or _text(payload.get("environment"))
        or _text(payload.get("region"))
        or _text(payload.get("forwarding_status"))
    )
    body: dict[str, Any] = {}
    for key in (
        "schema",
        "domain",
        "site_root",
        "environment",
        "region",
        "service_agreement_id",
        "configured",
        "forwarding_status",
        "gmail_send_as_status",
    ):
        if key in payload:
            body[key] = payload.get(key)
    if not body:
        body = _json_summary(payload)
    return [{"card_id": path.stem, "title": title, "summary": summary, "body": body}]


def build_service_tool_config_context(
    tool_id: str,
    *,
    private_dir: Path,
    tool_tabs: list[dict[str, Any]] | None,
    portal_instance_context: Any | None = None,
    portal_instance_id: str = "",
    msn_id: str = "",
) -> dict[str, Any]:
    definition = service_tool_definition(tool_id)
    if not definition:
        return {
            "ok": False,
            "schema": CONFIG_CONTEXT_SCHEMA,
            "error": f"Unsupported service tool: {_text(tool_id)}",
        }

    namespace = _text(definition.get("namespace"))
    root = _tool_root(private_dir, namespace)
    config_patterns = _expand_patterns(definition.get("config_patterns"), portal_instance_id=portal_instance_id)
    collection_patterns = _expand_patterns(definition.get("collection_patterns"), portal_instance_id=portal_instance_id)
    member_patterns = _expand_patterns(definition.get("member_patterns"), portal_instance_id=portal_instance_id)
    warnings: list[str] = []
    if not root.exists():
        warnings.append(f"tool state root is missing: {root}")

    config_datum: dict[str, Any] = {}
    collection_datum: dict[str, Any] = {}
    collection_members: list[dict[str, Any]] = []
    profile_cards: list[dict[str, Any]] = []
    collection_files: list[dict[str, Any]] = []
    if root.exists() and root.is_dir():
        config_path = _pick_canonical_file(root, config_patterns)
        collection_path = _pick_canonical_file(root, collection_patterns)
        config_datum, config_payload = _describe_file(root, config_path)
        collection_datum, collection_payload = _describe_file(root, collection_path)

        member_paths = _member_files_from_collection_payload(root, collection_payload)
        if not member_paths:
            member_paths = _iter_collection_files(root, member_patterns)

        seen_files: set[str] = set()
        for record in (config_datum, collection_datum):
            path_token = _text(record.get("path"))
            if path_token:
                seen_files.add(path_token)

        for path in member_paths:
            if str(path) in seen_files:
                continue
            seen_files.add(str(path))
            record, payload = _describe_file(root, path)
            if not record:
                continue
            collection_members.append(record)
            profile_cards.extend(_profile_cards_for_payload(path, payload))

        if config_datum and config_path is not None:
            profile_cards.extend(_profile_cards_for_payload(config_path, config_payload))
        if collection_datum and collection_path is not None and collection_path.name == "portal_instances.json":
            profile_cards.extend(_profile_cards_for_payload(collection_path, collection_payload))

        for record in (config_datum, collection_datum, *collection_members):
            if record:
                collection_files.append(record)

    if not config_datum:
        warnings.append(f"config datum is missing for tool namespace: {namespace}")
    if not collection_datum:
        warnings.append(f"collection datum is missing for tool namespace: {namespace}")

    service_contract = _service_tool_contract(definition, portal_instance_id=portal_instance_id)

    config_context = {
        "ok": True,
        "schema": CONFIG_CONTEXT_SCHEMA,
        "service_contract_schema": SERVICE_TOOL_CONTRACT_SCHEMA,
        "bindings_schema": SERVICE_TOOL_BINDINGS_SCHEMA,
        "tool_id": _text(tool_id).lower(),
        "shell_verb": "mediate",
        "portal_instance_id": _text(portal_instance_id),
        "msn_id": _text(msn_id),
        "portal_instance_context": _instance_payload(portal_instance_context),
        "binding_truth": "tool_state_files",
        "browse_truth": "tool_json_collection",
        "staging_truth": "tool_scoped_manual_edits",
        "commit_truth": "tool_state_files",
        "tool_namespace": namespace,
        "mediation_host_path": "/portal/system",
        "collection_root": str(root),
        "service_contract": service_contract,
        "config_datum": config_datum,
        "collection_datum": collection_datum,
        "collection_members": collection_members,
        "workspace_profile": {
            "workspace_id": _text(definition.get("workspace_id")),
            "label": _text(definition.get("label")),
            "default_mode": _text(definition.get("default_mode")) or "overview",
            "modes": list(definition.get("modes") or []),
        },
        "collection_files": collection_files,
        "profile_cards": profile_cards,
        "warnings": warnings,
        "activation": {
            "tool_id": _text(tool_id).lower(),
            "default_verb": "mediate",
            "can_open": bool(config_datum or collection_datum or collection_members),
            "host_path": "/portal/system",
            "request_payload": {"tool_id": _text(tool_id).lower(), "shell_verb": "mediate"},
        },
    }
    config_context["compatible_tools"] = compatible_tools_for_context(tool_tabs, config_context)
    config_context["inspector_cards"] = [
        build_inspector_card(
            card_id=f"{_text(tool_id).lower()}-collection",
            title="Tool Collections",
            summary=f"{len(collection_files)} file(s)",
            body={
                "tool_namespace": namespace,
                "config_datum": config_datum,
                "collection_datum": collection_datum,
                "collection_root": str(root),
                "files": collection_files,
                "warnings": warnings,
            },
            kind="mediation",
        ),
        build_inspector_card(
            card_id=f"{_text(tool_id).lower()}-profiles",
            title="Profile Cards",
            summary=f"{len(profile_cards)} card(s)",
            body={"cards": profile_cards[:20]},
            kind="metadata",
        ),
    ]
    return config_context


__all__ = [
    "SERVICE_TOOL_CONTRACT_SCHEMA",
    "SERVICE_TOOL_BINDINGS_SCHEMA",
    "build_service_tool_config_context",
    "build_service_tool_meta",
    "build_service_tool_registration",
    "service_tool_definition",
]
