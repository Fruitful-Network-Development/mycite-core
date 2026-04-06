from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from _shared.portal.application.internal_sources import derive_client_analytics_paths, read_internal_file
from _shared.portal.core_services.config_loader import load_active_private_config
from mycite_core.runtime_paths import utility_tools_dir
from mycite_core.state_machine.controls import CONFIG_CONTEXT_SCHEMA, build_inspector_card
from mycite_core.state_machine.tool_capabilities import compatible_tools_for_context
from packages.tools._shared.tool_contracts.service_catalog import (
    SERVICE_TOOL_BINDINGS_SCHEMA,
    SERVICE_TOOL_CONTRACT_SCHEMA,
    service_tool_definition,
)
from packages.tools.aws_csm.state_adapter.profile import normalize_aws_csm_profile_payload
from packages.tools.newsletter_admin.state_adapter import newsletter_domains, resolve_newsletter_domain_state


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()

def _instance_payload(portal_instance_context: Any | None) -> dict[str, Any]:
    if isinstance(portal_instance_context, dict):
        return {str(key): str(value) for key, value in portal_instance_context.items()}
    return {}


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
    namespace = _text(definition.get("namespace"))
    profile_schema = _text(definition.get("profile_schema"))
    return {
        "schema": SERVICE_TOOL_CONTRACT_SCHEMA,
        "tool_namespace": namespace,
        "profile_schema": _text(definition.get("profile_schema")),
        "mediation_host_path": "/portal/system",
        "anchor_contract": {
            "pattern": f"tool.<msn_id>.{namespace}.json" if namespace else "",
            "authoritative": "config.tools_configuration[].anchor",
            "compatibility_patterns": _expand_patterns(definition.get("config_patterns"), portal_instance_id=portal_instance_id),
        },
        "config_datum": {
            "patterns": _expand_patterns(definition.get("config_patterns"), portal_instance_id=portal_instance_id),
            "content_kind": "json",
        },
        "collection_datum": {
            "patterns": _expand_patterns(definition.get("collection_patterns"), portal_instance_id=portal_instance_id),
            "content_kind": "json_collection",
        },
        "member_datum": {
            "patterns": _expand_patterns(definition.get("member_patterns"), portal_instance_id=portal_instance_id),
            "content_kind": "mixed_collection",
        },
        "profile_card_contract": {
            "card_kind": "service_profile",
            "source": "tool_owned_datums",
            "profile_schema": profile_schema,
        },
        "internal_source_contract": {
            "mode": "read_only",
            "supported_content_kinds": ["json", "ndjson", "nginx_access_log", "nginx_error_log", "text"],
        },
        "collection_view_contract": {
            "default_mode": _text(definition.get("default_mode")) or "profiles",
            "modes": list(definition.get("modes") or []),
        },
        "host_composition": {
            "mode": "tool",
            "visible_regions": ["control_panel", "interface_panel"],
            "foreground_workbench": False,
            "background_workbench_runtime": True,
            "interface_panel_primary": True,
        },
    }


def build_service_tool_meta(tool_id: str) -> dict[str, Any]:
    definition = service_tool_definition(tool_id)
    if not definition:
        return {}
    lens_id = _text(definition.get("workspace_id") or definition.get("lens_id"))
    return {
        "supported_verbs": ["mediate"],
        "supported_source_contracts": [{"config_context": True}],
        "config_context_support": True,
        "source_resolution_rules": ["tool_json_collection", "profile_card_mediation"],
        "workbench_contribution": {},
        "interface_panel_contribution": {
            "lens_id": lens_id,
            "label": _text(definition.get("label")),
            "default_mode": _text(definition.get("default_mode")) or "overview",
            "modes": list(definition.get("modes") or []),
            "config_context_route": f"/portal/api/data/system/config_context/{_text(tool_id).lower()}",
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
        "shell_composition_mode": "tool",
        "foreground_surface": "interface_panel",
        "service_contract": _service_tool_contract(definition),
    }


def _tool_root(private_dir: Path, namespace: str) -> Path:
    return utility_tools_dir(private_dir) / namespace


def _anchor_candidates_from_config(private_dir: Path, namespace: str) -> list[str]:
    config = load_active_private_config(private_dir, None)
    if not isinstance(config, dict):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in list(config.get("tools_configuration") or []):
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name") or item.get("tool_id") or item.get("id")).lower().replace("_", "-")
        if name != _text(namespace).lower():
            continue
        anchor = _text(item.get("anchor"))
        if not anchor or anchor in seen:
            continue
        seen.add(anchor)
        out.append(anchor)
    return out


def _pick_config_anchor_file(private_dir: Path, root: Path, namespace: str, patterns: list[str]) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    candidates = _anchor_candidates_from_config(private_dir, namespace)
    for file_name in candidates:
        path = root / file_name
        if path.exists() and path.is_file():
            return path, warnings
        warnings.append(f"configured anchor is missing for {namespace}: {file_name}")
    fallback = _pick_canonical_file(root, patterns)
    return fallback, warnings


def _normalize_service_spec_payload(path: Path, payload: Any) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ({}, [f"invalid spec payload (expected JSON object): {path.name}"])
    normalized = dict(payload)
    if not _text(normalized.get("schema")):
        normalized["schema"] = "mycite.portal.tool_spec.v1"
        warnings.append(f"legacy minimal spec normalized with schema default: {path.name}")
    if not isinstance(normalized.get("inherited_inputs"), list):
        normalized["inherited_inputs"] = []
        warnings.append(f"spec missing inherited_inputs list; defaulted empty: {path.name}")
    if "outputs" not in normalized and isinstance(normalized.get("outputs_forms"), list):
        normalized["outputs"] = list(normalized.get("outputs_forms") or [])
        warnings.append(f"legacy outputs_forms mapped to outputs: {path.name}")
    if not isinstance(normalized.get("outputs"), list):
        normalized["outputs"] = []
    return normalized, warnings


def _classify_service_profile(path: Path, payload: Any, *, namespace: str, profile_schema: str) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ({}, ["profile payload must be a JSON object"], warnings)
    body = dict(payload)
    schema = _text(body.get("schema"))
    if not schema:
        body["schema"] = profile_schema
        warnings.append("profile schema was missing and has been defaulted")
    elif schema != profile_schema:
        warnings.append(f"non-canonical profile schema ({schema}); expected {profile_schema}")
    if namespace == "fnd-ebi":
        if not _text(body.get("domain")):
            errors.append("missing required field: domain")
        if not _text(body.get("site_root")):
            errors.append("missing required field: site_root")
    if namespace == "aws-csm":
        profile_hint = path.stem.removeprefix("aws-csm.")
        body, normalized_errors, normalized_warnings = normalize_aws_csm_profile_payload(body, profile_hint=profile_hint)
        errors.extend(normalized_errors)
        warnings.extend(normalized_warnings)
    return body, errors, warnings


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

    identity = payload.get("identity") if isinstance(payload.get("identity"), dict) else {}
    smtp = payload.get("smtp") if isinstance(payload.get("smtp"), dict) else {}
    verification = payload.get("verification") if isinstance(payload.get("verification"), dict) else {}
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
    inbound = payload.get("inbound") if isinstance(payload.get("inbound"), dict) else {}
    title = (
        _text(payload.get("title"))
        or _text(identity.get("send_as_email"))
        or _text(smtp.get("send_as_email"))
        or _text(payload.get("domain"))
        or _text(identity.get("domain"))
        or _text(payload.get("service_agreement_id"))
        or path.stem
    )
    summary = (
        _text(workflow.get("lifecycle_state"))
        or _text(workflow.get("handoff_status"))
        or _text(payload.get("schema"))
        or _text(payload.get("environment"))
        or _text(payload.get("region"))
        or _text(identity.get("region"))
        or _text(verification.get("status"))
        or _text(smtp.get("forwarding_status"))
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
        "identity",
        "smtp",
        "verification",
        "provider",
        "workflow",
        "inbound",
    ):
        if key in payload:
            body[key] = payload.get(key)
    if not body:
        body = _json_summary(payload)
    return [
        {
            "card_id": _text(identity.get("profile_id")) or path.stem,
            "title": title,
            "summary": summary,
            "body": body,
        }
    ]


def _fnd_ebi_profile_candidate(path: Path, payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if not _text(payload.get("site_root")):
        return False
    name = path.name.lower()
    return name.startswith("fnd-ebi.") and name.endswith(".json")


def _fnd_ebi_source_record(*, domain: str, source_key: str, result: Any) -> dict[str, Any]:
    path = Path(_text(getattr(result, "path", "")))
    file_name = path.name if path.name else source_key
    warnings = list(getattr(result, "warnings", []) or [])
    summary = getattr(result, "summary", {}) if isinstance(getattr(result, "summary", {}), dict) else {}
    return {
        "file_name": file_name,
        "relative_path": str(path),
        "path": str(path),
        "content_kind": _text(getattr(result, "content_kind", "")),
        "record_count": int(getattr(result, "record_count", 0) or 0),
        "schema": "",
        "summary": {
            "source_key": source_key,
            "domain": domain,
            "exists": bool(getattr(result, "exists", False)),
            "readable": bool(getattr(result, "readable", False)),
            "ok": bool(getattr(result, "ok", False)),
            "details": summary,
            "warnings": [str(item) for item in warnings if _text(item)],
        },
        "source_kind": "internal_file",
        "modified_utc": _text(summary.get("modified_utc")),
        "file_size_bytes": int(summary.get("file_size_bytes") or 0),
        "raw_line_count": int(summary.get("raw_line_count") or 0),
        "parsed_line_count": int(summary.get("parsed_line_count") or 0),
        "truncated": bool(summary.get("truncated")),
    }


def _parse_iso_utc(value: object) -> datetime | None:
    token = _text(value)
    if not token:
        return None
    try:
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _fnd_health_label(snapshot: dict[str, Any]) -> str:
    warnings = list(snapshot.get("warnings") or [])
    probe_count = int(((snapshot.get("traffic") or {}).get("suspicious_probe_count") or 0))
    requests_30d = int(((snapshot.get("traffic") or {}).get("requests_30d") or 0))
    events_30d = int(((snapshot.get("events_summary") or {}).get("events_30d") or 0))
    if warnings and any("stale" in _text(item).lower() for item in warnings):
        return "stale"
    if requests_30d > 0 and events_30d == 0:
        return "no events"
    if probe_count > 20 and probe_count > requests_30d // 2:
        return "scan-heavy"
    return "healthy"


def _fnd_source_state(source_key: str, result: Any) -> dict[str, Any]:
    summary = getattr(result, "summary", {}) if isinstance(getattr(result, "summary", {}), dict) else {}
    raw_line_count = int(summary.get("raw_line_count") or 0)
    parsed_line_count = int(summary.get("parsed_line_count") or 0)
    file_size_bytes = int(summary.get("file_size_bytes") or 0)
    exists = bool(getattr(result, "exists", False))
    readable = bool(getattr(result, "readable", False))
    modified_utc = _text(summary.get("modified_utc"))
    state = "missing"
    if exists and readable:
        state = "active" if raw_line_count > 0 or file_size_bytes > 0 else "empty"
    elif exists:
        state = "unreadable"
    if source_key == "events_file" and exists and readable and raw_line_count == 0 and file_size_bytes <= 1:
        state = "no_events_written"
    return {
        "path": _text(getattr(result, "path", "")),
        "present": exists,
        "readable": readable,
        "record_count": int(getattr(result, "record_count", 0) or 0),
        "raw_line_count": raw_line_count,
        "parsed_line_count": parsed_line_count,
        "truncated": bool(summary.get("truncated")),
        "truncated_line_count": int(summary.get("truncated_line_count") or 0),
        "file_size_bytes": file_size_bytes,
        "modified_utc": modified_utc,
        "last_seen_utc": _text(summary.get("last_seen_utc")),
        "state": state,
        "warnings": [str(item) for item in list(getattr(result, "warnings", []) or []) if _text(item)],
    }


def _fnd_frontend_diagnostics(site_root: str) -> dict[str, Any]:
    root = Path(_text(site_root))
    robots_path = root / "robots.txt"
    sitemap_paths = sorted(root.glob("sitemap*.xml")) if root.exists() and root.is_dir() else []
    instrumentation_hits: list[str] = []
    if root.exists() and root.is_dir():
        for pattern in ("*.html", "*.js"):
            for path in sorted(root.rglob(pattern)):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if any(token in text for token in ("/__fnd/collect", "/__fnd/analytics.js", "sendBeacon")):
                    instrumentation_hits.append(path.relative_to(root).as_posix())
                if len(instrumentation_hits) >= 8:
                    break
            if len(instrumentation_hits) >= 8:
                break
    return {
        "robots_present": robots_path.exists() and robots_path.is_file(),
        "robots_path": str(robots_path),
        "sitemap_present": bool(sitemap_paths),
        "sitemap_paths": [str(path) for path in sitemap_paths[:4]],
        "client_instrumentation_detected": bool(instrumentation_hits),
        "instrumentation_files": instrumentation_hits[:8],
    }


def _fnd_ebi_analytics_snapshot(path: Path, payload: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    domain = _text(payload.get("domain")) or path.stem
    site_root = _text(payload.get("site_root"))
    derivation = derive_client_analytics_paths(site_root)
    access_result = read_internal_file(derivation["access_log"], kind_hint="nginx_access_log")
    error_result = read_internal_file(derivation["error_log"], kind_hint="nginx_error_log")
    canonical_events_path = Path(derivation["events_file"])
    event_candidates = list(derivation.get("events_file_candidates") or [canonical_events_path])
    selected_events_path = canonical_events_path
    for candidate in event_candidates:
        try:
            candidate_path = Path(candidate)
        except Exception:
            continue
        if candidate_path.exists() and candidate_path.is_file():
            selected_events_path = candidate_path
            break
    events_result = read_internal_file(selected_events_path, kind_hint="ndjson")
    warnings: list[str] = []
    for result in (access_result, error_result, events_result):
        warnings.extend(str(item) for item in list(getattr(result, "warnings", []) or []) if _text(item))
    if selected_events_path != canonical_events_path:
        warnings.append(f"using legacy events path: {selected_events_path} (expected canonical {canonical_events_path})")
    access_summary = access_result.summary if isinstance(access_result.summary, dict) else {}
    error_summary = error_result.summary if isinstance(error_result.summary, dict) else {}
    event_summary = events_result.summary if isinstance(events_result.summary, dict) else {}
    frontend_summary = _fnd_frontend_diagnostics(site_root)
    access_state = _fnd_source_state("access_log", access_result)
    error_state = _fnd_source_state("error_log", error_result)
    events_state = _fnd_source_state("events_file", events_result)
    now_utc = datetime.now(timezone.utc)
    stale_cutoff = now_utc - timedelta(hours=72)
    access_last = _parse_iso_utc(access_summary.get("last_seen_utc"))
    error_last = _parse_iso_utc(error_summary.get("last_seen_utc"))
    events_last = _parse_iso_utc(event_summary.get("last_seen_utc"))
    if access_result.exists and (access_last is None or access_last < stale_cutoff):
        warnings.append("access log is stale")
    if error_result.exists and (error_last is None or error_last < stale_cutoff):
        warnings.append("error log is stale")
    if events_result.exists and (events_last is None or events_last < stale_cutoff):
        warnings.append("events file is stale")
    if not frontend_summary.get("client_instrumentation_detected"):
        warnings.append("frontend instrumentation not detected")
    if events_state.get("state") == "no_events_written":
        warnings.append("events file exists but has no records")
    elif not events_result.exists or int(event_summary.get("events_30d") or 0) == 0:
        warnings.append("no client events in current month file")
    if int(access_summary.get("robots_404_count") or 0) > 0:
        if frontend_summary.get("robots_present"):
            warnings.append("historical robots.txt 404s seen in access log, but file now exists")
        else:
            warnings.append("robots.txt requested but returning 404")
    if int(access_summary.get("sitemap_404_count") or 0) > 0:
        if frontend_summary.get("sitemap_present"):
            warnings.append("historical sitemap.xml 404s seen in access log, but file now exists")
        else:
            warnings.append("sitemap.xml requested but returning 404")
    if not frontend_summary.get("sitemap_present"):
        warnings.append("sitemap.xml is absent from frontend root")
    if int((access_summary.get("response_breakdown") or {}).get("4xx") or 0) > 100:
        warnings.append("high 404 scan noise observed")
    snapshot = {
        "domain": domain,
        "site_root": site_root,
        "analytics_root": str(derivation["analytics_root"]),
        "events_month": str(derivation["events_month_token"]).replace(".ndjson", ""),
        "access_log": access_state,
        "error_log": error_state,
        "events_file": events_state,
        "request_count_summary": int(access_result.record_count or 0),
        "error_count_summary": int(error_result.record_count or 0),
        "event_count_summary": int(events_result.record_count or 0),
        "frontend": frontend_summary,
        "freshness": {
            "access_last_seen_utc": _text(access_summary.get("last_seen_utc")),
            "error_last_seen_utc": _text(error_summary.get("last_seen_utc")),
            "events_last_seen_utc": _text(event_summary.get("last_seen_utc")),
        },
        "acquisition": {
            "access_log": access_state,
            "error_log": error_state,
            "events_file": events_state,
            "frontend": frontend_summary,
        },
        "traffic": {
            "requests_24h": int(access_summary.get("requests_24h") or 0),
            "requests_7d": int(access_summary.get("requests_7d") or 0),
            "requests_30d": int(access_summary.get("requests_30d") or 0),
            "unique_visitors_approx_30d": int(access_summary.get("unique_visitors_approx_30d") or 0),
            "response_breakdown": {
                "2xx": int((access_summary.get("response_breakdown") or {}).get("2xx") or 0),
                "3xx": int((access_summary.get("response_breakdown") or {}).get("3xx") or 0),
                "4xx": int((access_summary.get("response_breakdown") or {}).get("4xx") or 0),
                "5xx": int((access_summary.get("response_breakdown") or {}).get("5xx") or 0),
            },
            "bot_share": float(access_summary.get("bot_share") or 0.0),
            "bot_requests": int(access_summary.get("bot_requests") or 0),
            "suspicious_probe_count": int(access_summary.get("suspicious_probe_count") or 0),
            "real_page_requests_30d": int(access_summary.get("real_page_requests_30d") or 0),
            "asset_vs_page": {
                "asset_requests": int((access_summary.get("asset_vs_page") or {}).get("asset_requests") or 0),
                "page_requests": int((access_summary.get("asset_vs_page") or {}).get("page_requests") or 0),
            },
            "top_pages": list(access_summary.get("top_pages") or []),
            "top_requested_paths": list(access_summary.get("top_requested_paths") or []),
            "top_referrers": list(access_summary.get("top_referrers") or []),
            "trend_7d": list(access_summary.get("trend_7d") or []),
            "trend_30d": list(access_summary.get("trend_30d") or []),
        },
        "events_summary": {
            "events_24h": int(event_summary.get("events_24h") or 0),
            "events_7d": int(event_summary.get("events_7d") or 0),
            "events_30d": int(event_summary.get("events_30d") or 0),
            "session_count_approx": int(event_summary.get("session_count_approx") or 0),
            "event_type_counts": dict(event_summary.get("event_type_counts") or {}),
            "trend_7d": list(event_summary.get("trend_7d") or []),
            "trend_30d": list(event_summary.get("trend_30d") or []),
        },
        "errors_noise": {
            "error_severity_counts": dict(error_summary.get("severity_counts") or {}),
            "top_error_routes": list(access_summary.get("top_error_routes") or []),
            "top_site_error_routes": list(access_summary.get("top_site_error_routes") or []),
            "top_asset_error_routes": list(access_summary.get("top_asset_error_routes") or []),
            "top_probe_routes": list(access_summary.get("top_probe_routes") or []),
            "suspicious_probe_examples": list(access_summary.get("suspicious_probe_examples") or []),
        },
        "warnings": warnings,
    }
    snapshot["health_label"] = _fnd_health_label(snapshot)
    records = [
        _fnd_ebi_source_record(domain=domain, source_key="access_log", result=access_result),
        _fnd_ebi_source_record(domain=domain, source_key="error_log", result=error_result),
        _fnd_ebi_source_record(domain=domain, source_key="events_file", result=events_result),
    ]
    return snapshot, records


def _merge_fnd_ebi_snapshots_into_cards(profile_cards: list[dict[str, Any]], snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_domain = {_text(item.get("domain")).lower(): dict(item) for item in snapshots if isinstance(item, dict)}
    out: list[dict[str, Any]] = []
    for card in profile_cards:
        if not isinstance(card, dict):
            continue
        body = dict(card.get("body")) if isinstance(card.get("body"), dict) else {}
        token = _text(body.get("domain") or card.get("title")).lower()
        snapshot = by_domain.get(token)
        if snapshot:
            body["analytics_snapshot"] = snapshot
            card = {**card, "body": body}
        out.append(card)
    return out


def _service_profile_interface_cards(namespace: str, profile_cards: list[dict[str, Any]], analytics_snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if namespace == "fnd-ebi":
        for snapshot in analytics_snapshots:
            if not isinstance(snapshot, dict):
                continue
            domain = _text(snapshot.get("domain")) or "site"
            traffic = snapshot.get("traffic") if isinstance(snapshot.get("traffic"), dict) else {}
            events_summary = snapshot.get("events_summary") if isinstance(snapshot.get("events_summary"), dict) else {}
            errors_noise = snapshot.get("errors_noise") if isinstance(snapshot.get("errors_noise"), dict) else {}
            access_state = snapshot.get("access_log") if isinstance(snapshot.get("access_log"), dict) else {}
            error_state = snapshot.get("error_log") if isinstance(snapshot.get("error_log"), dict) else {}
            events_state = snapshot.get("events_file") if isinstance(snapshot.get("events_file"), dict) else {}
            out.append(
                build_inspector_card(
                    card_id=f"fnd-ebi-profile-{domain}",
                    title=domain,
                    summary=_text(snapshot.get("health_label")) or "analytics",
                    kind="profile",
                    body={
                        "domain": domain,
                        "site_root": _text(snapshot.get("site_root")),
                        "analytics_root": _text(snapshot.get("analytics_root")),
                        "access_log": {
                            "path": _text(access_state.get("path")),
                            "present": bool(access_state.get("present")),
                            "readable": bool(access_state.get("readable")),
                        },
                        "error_log": {
                            "path": _text(error_state.get("path")),
                            "present": bool(error_state.get("present")),
                            "readable": bool(error_state.get("readable")),
                        },
                        "events_file": {
                            "path": _text(events_state.get("path")),
                            "present": bool(events_state.get("present")),
                            "readable": bool(events_state.get("readable")),
                        },
                        "traffic_summary": {
                            "requests_30d": int(traffic.get("requests_30d") or 0),
                            "unique_visitors_approx_30d": int(traffic.get("unique_visitors_approx_30d") or 0),
                            "bot_share": float(traffic.get("bot_share") or 0.0),
                            "response_breakdown": dict(traffic.get("response_breakdown") or {}),
                        },
                        "event_summary": {
                            "events_30d": int(events_summary.get("events_30d") or 0),
                            "event_type_counts": dict(events_summary.get("event_type_counts") or {}),
                        },
                        "errors_noise": {
                            "error_severity_counts": dict(errors_noise.get("error_severity_counts") or {}),
                            "suspicious_probe_examples": list(errors_noise.get("suspicious_probe_examples") or []),
                        },
                        "warnings": list(snapshot.get("warnings") or []),
                    },
                )
            )
    if namespace == "aws-csm":
        for card in profile_cards:
            if not isinstance(card, dict):
                continue
            body = dict(card.get("body")) if isinstance(card.get("body"), dict) else {}
            identity = dict(body.get("identity")) if isinstance(body.get("identity"), dict) else {}
            smtp = dict(body.get("smtp")) if isinstance(body.get("smtp"), dict) else {}
            verification = dict(body.get("verification")) if isinstance(body.get("verification"), dict) else {}
            provider = dict(body.get("provider")) if isinstance(body.get("provider"), dict) else {}
            workflow = dict(body.get("workflow")) if isinstance(body.get("workflow"), dict) else {}
            title = _text(card.get("title")) or _text(identity.get("domain")) or _text(card.get("card_id")) or "profile"
            handoff_status = _text(workflow.get("handoff_status"))
            summary = "staging required"
            if handoff_status == "ready_for_gmail_handoff":
                summary = "gmail handoff"
            elif handoff_status == "send_as_confirmed":
                summary = "confirmed"
            out.append(
                build_inspector_card(
                    card_id=f"aws-csm-profile-{_text(card.get('card_id')) or title}",
                    title=title,
                    summary=summary,
                    kind="profile",
                    body={
                        "identity": identity,
                        "smtp": smtp,
                        "verification": verification,
                        "provider": provider,
                        "workflow": workflow,
                    },
                )
            )
    return out

def _aws_newsletter_cards(private_dir: Path) -> list[dict[str, Any]]:
    progeny_root = private_dir / "network" / "progeny"
    if not progeny_root.exists() or not progeny_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for path in sorted(progeny_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        refs = payload.get("profile_refs") if isinstance(payload.get("profile_refs"), dict) else {}
        policy = payload.get("email_policy") if isinstance(payload.get("email_policy"), dict) else {}
        newsletter = policy.get("newsletter") if isinstance(policy.get("newsletter"), dict) else {}
        sender_address = _text(newsletter.get("sender_address") or refs.get("newsletter_sender_address"))
        ingest_address = _text(newsletter.get("ingest_address") or refs.get("newsletter_ingest_address"))
        allowed_from = list(newsletter.get("allowed_from") or []) if isinstance(newsletter.get("allowed_from"), list) else []
        allowed_from_csv = _text(refs.get("newsletter_allowed_from_csv")) or ", ".join(
            [_text(item) for item in allowed_from if _text(item)]
        )
        dispatch_mode = _text(newsletter.get("dispatch_mode") or refs.get("newsletter_dispatch_mode")) or "aws_internal"
        domain = ""
        if "@" in sender_address:
            domain = sender_address.split("@", 1)[1].strip().lower()
        elif "@" in ingest_address:
            domain = ingest_address.split("@", 1)[1].strip().lower()
        else:
            domain = _text(refs.get("paypal_site_domain")).lower()
        if not domain or not (sender_address or ingest_address):
            continue
        dedupe_key = (domain, sender_address.lower(), ingest_address.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        out.append(
            {
                "card_id": f"aws-csm.newsletter.{domain}",
                "kind": "newsletter",
                "domain": domain,
                "title": sender_address or f"newsletter@{domain}",
                "sender_address": sender_address,
                "ingest_address": ingest_address,
                "allowed_from_csv": allowed_from_csv,
                "dispatch_mode": dispatch_mode,
                "source_path": str(path),
            }
        )
    return out


def _aws_profile_domain_sections(profile_cards: list[dict[str, Any]], *, private_dir: Path | None = None) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in profile_cards:
        if not isinstance(card, dict):
            continue
        body = dict(card.get("body")) if isinstance(card.get("body"), dict) else {}
        identity = dict(body.get("identity")) if isinstance(body.get("identity"), dict) else {}
        domain = _text(identity.get("domain")) or "unscoped"
        grouped.setdefault(domain, []).append(card)
    newsletters_by_domain: dict[str, list[dict[str, Any]]] = {}
    if isinstance(private_dir, Path):
        for card in _aws_newsletter_cards(private_dir):
            domain = _text(card.get("domain")) or "unscoped"
            newsletters_by_domain.setdefault(domain, []).append(card)
    out: list[dict[str, Any]] = []
    all_domains = sorted(set(grouped.keys()) | set(newsletters_by_domain.keys()), key=lambda item: item.lower())
    for domain in all_domains:
        cards = sorted(
            grouped.get(domain) or [],
            key=lambda item: (
                _text((((item.get("body") or {}) if isinstance(item.get("body"), dict) else {}).get("identity") or {}).get("mailbox_local_part")).lower(),
                _text(item.get("title")).lower(),
                _text(item.get("card_id")).lower(),
            ),
        )
        newsletter_cards = sorted(
            newsletters_by_domain.get(domain) or [],
            key=lambda item: (_text(item.get("title")).lower(), _text(item.get("sender_address")).lower()),
        )
        out.append(
            {
                "domain": domain,
                "card_count": len(cards),
                "cards": cards,
                "newsletter_cards": newsletter_cards,
            }
        )
    return out


def _newsletter_profile_cards(private_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    cards: list[dict[str, Any]] = []
    derived_members: list[dict[str, Any]] = []
    warnings: list[str] = []
    for domain in newsletter_domains(private_dir):
        state = resolve_newsletter_domain_state(private_dir, domain)
        selected_sender = dict(state.get("selected_sender") or {})
        summary = f"{int(state.get('subscribed_count') or 0)} subscribed"
        if _text(selected_sender.get("send_as_email")):
            summary += f" · sender {selected_sender.get('send_as_email')}"
        cards.append(
            build_inspector_card(
                card_id=f"newsletter-admin.{domain}",
                title=domain,
                summary=summary,
                kind="profile",
                body={
                    "domain": domain,
                    "contact_log_path": _text(state.get("contact_log_path")),
                    "profile_path": _text(state.get("profile_path")),
                    "list_address": _text(state.get("list_address")),
                    "selected_sender": selected_sender,
                    "verified_senders": list(state.get("verified_senders") or []),
                    "contacts": list(state.get("contacts") or []),
                    "contacts_preview": list(state.get("contacts_preview") or []),
                    "dispatches": list(state.get("dispatches") or []),
                    "latest_dispatch": dict(state.get("latest_dispatch") or {}),
                    "contact_count": int(state.get("contact_count") or 0),
                    "subscribed_count": int(state.get("subscribed_count") or 0),
                    "unsubscribed_count": int(state.get("unsubscribed_count") or 0),
                },
            )
        )
        contact_log_path = Path(_text(state.get("contact_log_path")))
        if contact_log_path.exists() and contact_log_path.is_file():
            kind, payload = _load_json_or_lines(contact_log_path)
            derived_members.append(
                {
                    "file_name": contact_log_path.name,
                    "relative_path": str(contact_log_path),
                    "path": str(contact_log_path),
                    "content_kind": kind,
                    "record_count": len((payload or {}).get("contacts") or []) if isinstance(payload, dict) else 1,
                    "schema": _text(payload.get("schema")) if isinstance(payload, dict) else "",
                    "summary": _json_summary(payload),
                }
            )
        else:
            warnings.append(f"contact log is missing for newsletter domain: {domain}")
    return cards, derived_members, warnings


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
    analytics_snapshots: list[dict[str, Any]] = []
    derived_internal_members: list[dict[str, Any]] = []
    candidate_profiles: list[tuple[Path, Any]] = []
    if root.exists() and root.is_dir():
        config_path, anchor_warnings = _pick_config_anchor_file(private_dir, root, namespace, config_patterns)
        warnings.extend(anchor_warnings)
        collection_path = _pick_canonical_file(root, collection_patterns)
        config_datum, config_payload = _describe_file(root, config_path)
        collection_datum, collection_payload = _describe_file(root, collection_path)
        profile_schema = _text(definition.get("profile_schema"))

        spec_path = root / "spec.json"
        if spec_path.exists() and spec_path.is_file():
            spec_record, spec_payload = _describe_file(root, spec_path)
            normalized_spec, spec_warnings = _normalize_service_spec_payload(spec_path, spec_payload)
            warnings.extend(spec_warnings)
            if spec_record:
                spec_record["summary"] = _json_summary(normalized_spec)
                collection_members.append(spec_record)
                seen_files: set[str] = {_text(spec_record.get("path"))} if _text(spec_record.get("path")) else set()
            else:
                seen_files = set()
        else:
            warnings.append(f"spec.json is missing for tool namespace: {namespace}")
            seen_files = set()

        member_paths = _member_files_from_collection_payload(root, collection_payload)
        if not member_paths:
            member_paths = _iter_collection_files(root, member_patterns)
        if collection_path is not None and collection_path.name == "web-analytics.json":
            warnings.append("compatibility collection in use: web-analytics.json (anchor is canonical)")
        if collection_path is not None and collection_path.name == "aws-csm.collection.json":
            warnings.append("compatibility collection in use: aws-csm.collection.json (anchor is canonical)")

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
            if path.name == "spec.json":
                continue
            collection_members.append(record)
            if path.name.startswith("tool.") and path.name.endswith(f".{namespace}.json"):
                continue
            normalized_payload, profile_errors, profile_warnings = _classify_service_profile(
                path,
                payload,
                namespace=namespace,
                profile_schema=profile_schema,
            )
            if profile_errors:
                warnings.extend([f"{path.name}: {item}" for item in profile_errors])
            if profile_warnings:
                warnings.extend([f"{path.name}: {item}" for item in profile_warnings])
            record["summary"] = _json_summary(normalized_payload if isinstance(normalized_payload, dict) else payload)
            profile_cards.extend(_profile_cards_for_payload(path, normalized_payload))
            if namespace == "fnd-ebi" and _fnd_ebi_profile_candidate(path, payload):
                candidate_profiles.append((path, normalized_payload))

        if config_datum and config_path is not None:
            config_name = config_path.name
            if not (config_name.startswith("tool.") and config_name.endswith(f".{namespace}.json")):
                normalized_payload, profile_errors, profile_warnings = _classify_service_profile(
                    config_path,
                    config_payload,
                    namespace=namespace,
                    profile_schema=profile_schema,
                )
                if profile_errors:
                    warnings.extend([f"{config_name}: {item}" for item in profile_errors])
                if profile_warnings:
                    warnings.extend([f"{config_name}: {item}" for item in profile_warnings])
                profile_cards.extend(_profile_cards_for_payload(config_path, normalized_payload))
                if namespace == "fnd-ebi" and _fnd_ebi_profile_candidate(config_path, normalized_payload):
                    candidate_profiles.append((config_path, normalized_payload))
        if collection_datum and collection_path is not None and collection_path.name == "portal_instances.json":
            profile_cards.extend(_profile_cards_for_payload(collection_path, collection_payload))

        if namespace == "fnd-ebi":
            for profile_path, profile_payload in candidate_profiles:
                snapshot, records = _fnd_ebi_analytics_snapshot(profile_path, profile_payload)
                analytics_snapshots.append(snapshot)
                derived_internal_members.extend(records)
                for item in list(snapshot.get("warnings") or []):
                    token = _text(item)
                    if token:
                        warnings.append(f"{snapshot.get('domain')}: {token}")
            profile_cards = _merge_fnd_ebi_snapshots_into_cards(profile_cards, analytics_snapshots)
            collection_members.extend(derived_internal_members)
        if namespace == "newsletter-admin":
            newsletter_cards, newsletter_members, newsletter_warnings = _newsletter_profile_cards(private_dir)
            profile_cards = newsletter_cards
            derived_internal_members.extend(newsletter_members)
            collection_members.extend(newsletter_members)
            warnings.extend(newsletter_warnings)

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
        "shell_composition_mode": "tool",
        "foreground_surface": "interface_panel",
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
        "interface_lens": {
            "lens_id": _text(definition.get("workspace_id") or definition.get("lens_id")),
            "label": _text(definition.get("label")),
            "default_mode": _text(definition.get("default_mode")) or "overview",
            "modes": list(definition.get("modes") or []),
            "shell_composition_mode": "tool",
            "foreground_surface": "interface_panel",
        },
        "collection_files": collection_files,
        "profile_cards": profile_cards,
        "profile_domain_sections": _aws_profile_domain_sections(profile_cards, private_dir=private_dir) if namespace == "aws-csm" else [],
        "derived_internal_members": derived_internal_members,
        "analytics_snapshots": analytics_snapshots,
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
                "derived_internal_members": derived_internal_members,
                "warnings": warnings,
            },
            kind="mediation",
        ),
        build_inspector_card(
            card_id=f"{_text(tool_id).lower()}-profiles",
            title="Profile Cards",
            summary=f"{len(profile_cards)} card(s)",
            body={"cards": profile_cards[:20], "analytics_snapshots": analytics_snapshots[:20]},
            kind="metadata",
        ),
    ]
    config_context["inspector_cards"].extend(
        _service_profile_interface_cards(
            namespace=namespace,
            profile_cards=profile_cards,
            analytics_snapshots=analytics_snapshots,
        )
    )
    return config_context


__all__ = [
    "SERVICE_TOOL_CONTRACT_SCHEMA",
    "SERVICE_TOOL_BINDINGS_SCHEMA",
    "build_service_tool_config_context",
    "build_service_tool_meta",
    "build_service_tool_registration",
    "service_tool_definition",
]
