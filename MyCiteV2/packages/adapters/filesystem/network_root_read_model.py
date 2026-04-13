from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from MyCiteV2.packages.ports.network_root_read_model import (
    NetworkRootReadModelPort,
    NetworkRootReadModelRequest,
    NetworkRootReadModelResult,
    NetworkRootReadModelSource,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_read_json(path: Path, *, warnings: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    if not path.is_file():
        warnings.append(f"{label} is not a file: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"Failed to read {label}: {path.name} ({exc})")
        return {}
    if not isinstance(payload, dict):
        warnings.append(f"{label} must contain a JSON object: {path.name}")
        return {}
    return payload


def _parse_any_timestamp(value: object) -> datetime | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number <= 0:
            return None
        if number > 10_000_000_000:
            number = number / 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except Exception:
            return None
    token = _as_text(value)
    if not token:
        return None
    if token.isdigit():
        return _parse_any_timestamp(int(token))
    try:
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        parsed = datetime.fromisoformat(token)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _format_timestamp(value: object) -> str:
    parsed = _parse_any_timestamp(value)
    if parsed is None:
        return ""
    return parsed.isoformat().replace("+00:00", "Z")


def _iter_json_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    out: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except Exception:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            if child.is_dir():
                stack.append(child)
                continue
            if child.suffix.lower() == ".json":
                out.append(child)
    return sorted(out, key=lambda item: str(item))


def _iter_ndjson_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name.startswith(".") or not child.is_file():
            continue
        if child.suffix.lower() == ".ndjson":
            out.append(child)
    return out


def _line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except Exception:
        return 0


def _top_rows(source: dict[str, int], key_name: str) -> list[dict[str, Any]]:
    rows = sorted(source.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return [{key_name: key, "count": int(count)} for key, count in rows[:8]]


def _request_log_counterparty(payload: dict[str, Any], *, local_msn_id: str) -> str:
    for key in ("counterparty_msn_id", "client_msn_id", "company_msn_id", "receiver", "transmitter"):
        token = _as_text(payload.get(key))
        if token and token != local_msn_id and token != f"msn-{local_msn_id}":
            return token.removeprefix("msn-")
    details = payload.get("details")
    if isinstance(details, dict):
        proposal = details.get("proposal")
        if isinstance(proposal, dict):
            for key in ("receiver_msn_id", "sender_msn_id"):
                token = _as_text(proposal.get(key))
                if token and token != local_msn_id:
                    return token
        confirmation = details.get("confirmation")
        if isinstance(confirmation, dict):
            for key in ("receiver_msn_id", "sender_msn_id"):
                token = _as_text(confirmation.get(key))
                if token and token != local_msn_id:
                    return token
    return ""


def _summarize_request_logs(request_log_dir: Path, external_event_dir: Path, *, local_msn_id: str, warnings: list[str]) -> dict[str, Any]:
    file_count = 0
    event_count = 0
    type_counts: dict[str, int] = {}
    counterparty_counts: dict[str, int] = {}
    recent_events: list[dict[str, Any]] = []
    latest_event_at = ""

    for path in _iter_ndjson_files(request_log_dir):
        file_count += 1
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            warnings.append(f"Failed to read request-log file {path.name}: {exc}")
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            event_count += 1
            event_type = _as_text(payload.get("type") or payload.get("event_type") or payload.get("schema")) or "unknown"
            type_counts[event_type] = int(type_counts.get(event_type) or 0) + 1
            counterparty = _request_log_counterparty(payload, local_msn_id=local_msn_id)
            if counterparty:
                counterparty_counts[counterparty] = int(counterparty_counts.get(counterparty) or 0) + 1
            timestamp = _format_timestamp(
                payload.get("ts_unix_ms")
                or payload.get("received_at_unix_ms")
                or payload.get("timestamp")
                or payload.get("ts")
                or payload.get("created_unix_ms")
            )
            if timestamp and timestamp > latest_event_at:
                latest_event_at = timestamp
            recent_events.append(
                {
                    "timestamp": timestamp or "",
                    "type": event_type,
                    "status": _as_text(payload.get("status")) or "—",
                    "counterparty": counterparty,
                }
            )

    recent_events_sorted = sorted(
        recent_events,
        key=lambda item: str(item.get("timestamp") or ""),
        reverse=True,
    )[:8]

    external_event_entry_count = 0
    if external_event_dir.exists() and external_event_dir.is_dir():
        try:
            external_event_entry_count = len([item for item in external_event_dir.iterdir() if not item.name.startswith(".")])
        except Exception:
            external_event_entry_count = 0

    return {
        "state": "ready" if request_log_dir.exists() else "not_configured",
        "request_log_dir": str(request_log_dir),
        "external_event_dir": str(external_event_dir),
        "file_count": file_count,
        "event_count": event_count,
        "latest_event_at": latest_event_at,
        "top_event_types": _top_rows(type_counts, "type"),
        "counterparties": _top_rows(counterparty_counts, "counterparty"),
        "recent_events": recent_events_sorted,
        "external_event_entry_count": external_event_entry_count,
    }


def _local_audit_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "path": "",
            "state": "not_configured",
            "line_count": 0,
        }
    if not path.exists():
        return {
            "path": str(path),
            "state": "missing_or_empty",
            "line_count": 0,
        }
    return {
        "path": str(path),
        "state": "present",
        "line_count": _line_count(path),
    }


def _hosted_manifest_summary(hosted_manifest: dict[str, Any]) -> dict[str, Any]:
    type_values = hosted_manifest.get("type_values")
    if not isinstance(type_values, dict):
        type_values = {}
    subject = hosted_manifest.get("subject_congregation")
    if not isinstance(subject, dict):
        subject = {}
    tabs = subject.get("tabs")
    if not isinstance(tabs, list):
        tabs = []
    orientation = type_values.get("orientation")
    if not isinstance(orientation, dict):
        orientation = {}
    return {
        "layout": _as_text(hosted_manifest.get("type") or "subject_congregation"),
        "orientation_title": _as_text(subject.get("hero_title") or orientation.get("hero_title")),
        "subject_tabs": [_as_text(tab.get("label") or tab.get("id")) for tab in tabs if isinstance(tab, dict) and (_as_text(tab.get("label")) or _as_text(tab.get("id")))],
        "default_hosted_count": len(list(type_values.get("default_hosted") or [])),
        "channel_count": len(list(type_values.get("channels") or [])),
    }


class FilesystemNetworkRootReadModelAdapter(NetworkRootReadModelPort):
    def __init__(
        self,
        *,
        private_dir: str | Path | None,
        local_audit_file: str | Path | None = None,
    ) -> None:
        self._private_dir = None if private_dir is None else Path(private_dir)
        self._local_audit_file = None if local_audit_file is None else Path(local_audit_file)

    def read_network_root_model(self, request: NetworkRootReadModelRequest) -> NetworkRootReadModelResult:
        warnings: list[str] = []
        private_dir = self._private_dir
        if private_dir is None:
            payload = {
                "portal_instance": {
                    "portal_instance_id": request.portal_tenant_id,
                    "audience": "trusted_tenant_plus_internal_admin",
                    "runtime_flavor": "v2_native",
                    "domain": request.portal_domain,
                    "deployment_state": "runtime_only",
                    "msn_id": "",
                },
                "host_aliases": [],
                "progeny_links": [],
                "p2p_contracts": [],
                "external_service_bindings": [],
                "profile_projections": [],
                "request_log_summary": {
                    "state": "not_configured",
                    "request_log_dir": "",
                    "external_event_dir": "",
                    "file_count": 0,
                    "event_count": 0,
                    "latest_event_at": "",
                    "top_event_types": [],
                    "counterparties": [],
                    "recent_events": [],
                    "external_event_entry_count": 0,
                },
                "local_audit_summary": _local_audit_summary(self._local_audit_file),
                "hosted_manifest_summary": {
                    "layout": "subject_congregation",
                    "orientation_title": "",
                    "subject_tabs": [],
                    "default_hosted_count": 0,
                    "channel_count": 0,
                },
                "warnings": ["private_dir was not configured for the network root read model."],
            }
            return NetworkRootReadModelResult(source=NetworkRootReadModelSource(payload=payload))

        config = _safe_read_json(private_dir / "config.json", warnings=warnings, label="private/config.json")
        hosted_manifest = _safe_read_json(
            private_dir / "network" / "hosted.json",
            warnings=warnings,
            label="private/network/hosted.json",
        )
        local_msn_id = _as_text(config.get("msn_id"))

        host_aliases: list[dict[str, Any]] = []
        profile_projections: list[dict[str, Any]] = []
        for path in _iter_json_files(private_dir / "network" / "aliases"):
            payload = _safe_read_json(path, warnings=warnings, label=f"alias file {path.name}")
            fields = payload.get("fields")
            if not isinstance(fields, dict):
                fields = {}
            host_alias_id = _as_text(payload.get("alias_id")) or path.stem
            host_aliases.append(
                {
                    "host_alias_id": host_alias_id,
                    "portal_instance_id": request.portal_tenant_id,
                    "alias_kind": f"{_as_text(payload.get('progeny_type')) or 'network'}_alias",
                    "projection_state": _as_text(payload.get("status")) or "unknown",
                    "provider_truth_source": f"private/network/aliases/{path.name}",
                    "host_title": _as_text(payload.get("host_title")),
                    "alias_host": _as_text(payload.get("alias_host")),
                    "contract_id": _as_text(payload.get("contract_id")),
                    "child_msn_id": _as_text(payload.get("child_msn_id") or payload.get("member_msn_id")),
                }
            )
            profile_projections.append(
                {
                    "projection_id": host_alias_id,
                    "projection_kind": "host_alias_projection",
                    "state": _as_text(payload.get("status")) or "unknown",
                    "title": _as_text(payload.get("host_title")) or host_alias_id,
                    "contract_ref": _as_text(payload.get("contract_id")),
                    "workspace_layout": _as_text(fields.get("workspace_layout")),
                }
            )

        progeny_links: list[dict[str, Any]] = []
        for path in _iter_json_files(private_dir / "network" / "progeny"):
            payload = _safe_read_json(path, warnings=warnings, label=f"progeny file {path.name}")
            contract = payload.get("contract")
            if not isinstance(contract, dict):
                contract = {}
            status = payload.get("status")
            if not isinstance(status, dict):
                status = {}
            progeny_link_id = _as_text(payload.get("progeny_id")) or path.stem
            relationship_kind = _as_text(payload.get("progeny_type") or payload.get("profile_type")) or "derived_member"
            target_portal_instance_id = _as_text(contract.get("counterparty_msn_id") or payload.get("msn_id"))
            contract_state = _as_text(contract.get("status") or status.get("state")) or "unknown"
            title = _as_text(payload.get("title"))
            display = payload.get("display")
            if not title and isinstance(display, dict):
                title = _as_text(display.get("title"))
            progeny_links.append(
                {
                    "progeny_link_id": progeny_link_id,
                    "source_portal_instance_id": request.portal_tenant_id,
                    "target_portal_instance_id": target_portal_instance_id,
                    "relationship_kind": relationship_kind,
                    "contract_state": contract_state,
                    "title": title,
                }
            )
            contract_refs = payload.get("contract_refs")
            if not isinstance(contract_refs, dict):
                contract_refs = {}
            profile_projections.append(
                {
                    "projection_id": progeny_link_id,
                    "projection_kind": relationship_kind,
                    "state": contract_state,
                    "title": title,
                    "contract_ref": _as_text(contract.get("contract_id") or contract_refs.get("authorization_contract_id")),
                }
            )

        request_log_summary = _summarize_request_logs(
            private_dir / "network" / "request_log",
            private_dir / "network" / "external_events",
            local_msn_id=local_msn_id,
            warnings=warnings,
        )
        evidence_state = "request_log_present" if int(request_log_summary.get("event_count") or 0) > 0 else "filesystem_recorded"

        p2p_contracts: list[dict[str, Any]] = []
        for path in _iter_json_files(private_dir / "contracts"):
            payload = _safe_read_json(path, warnings=warnings, label=f"contract file {path.name}")
            contract_id = _as_text(payload.get("contract_id")) or path.stem
            p2p_contracts.append(
                {
                    "p2p_contract_id": contract_id,
                    "authority_scope": _as_text(payload.get("contract_type")) or "unknown",
                    "relationship_kind": _as_text(payload.get("contract_type")) or "unknown",
                    "evidence_state": evidence_state,
                    "enforcement_state": _as_text(payload.get("status")) or "unknown",
                    "counterparty_msn_id": _as_text(payload.get("counterparty_msn_id")),
                    "tracked_resource_count": len(list(payload.get("tracked_resource_ids") or [])),
                }
            )

        external_service_bindings: list[dict[str, Any]] = []
        config_hosted = config.get("hosted")
        if isinstance(config_hosted, dict) and config_hosted:
            external_service_bindings.append(
                {
                    "binding_id": f"{request.portal_tenant_id}.hosted.config",
                    "binding_family": "portal_hosting",
                    "subject_id": request.portal_tenant_id,
                    "provider_kind": _as_text(config_hosted.get("hosting_type")) or "portal_hosted",
                    "binding_state": "configured",
                }
            )
        hosted_aws = hosted_manifest.get("aws")
        if isinstance(hosted_aws, dict) and hosted_aws:
            external_service_bindings.append(
                {
                    "binding_id": f"{request.portal_tenant_id}.aws",
                    "binding_family": "aws_mail_transport",
                    "subject_id": request.portal_tenant_id,
                    "provider_kind": "aws",
                    "binding_state": _as_text(hosted_aws.get("email_transport_mode")) or "configured",
                }
            )
        workflow = hosted_manifest.get("workflow")
        if isinstance(workflow, dict) and workflow:
            external_service_bindings.append(
                {
                    "binding_id": f"{request.portal_tenant_id}.workflow",
                    "binding_family": "hosted_workflow",
                    "subject_id": request.portal_tenant_id,
                    "provider_kind": _as_text(workflow.get("analytics_provider")) or "workflow",
                    "binding_state": "configured",
                }
            )
        broadcaster = hosted_manifest.get("broadcaster")
        if isinstance(broadcaster, dict) and broadcaster:
            external_service_bindings.append(
                {
                    "binding_id": f"{request.portal_tenant_id}.broadcaster",
                    "binding_family": "hosted_broadcaster",
                    "subject_id": request.portal_tenant_id,
                    "provider_kind": "broadcaster",
                    "binding_state": "enabled" if broadcaster.get("enabled") else "disabled",
                }
            )

        payload = {
            "portal_instance": {
                "portal_instance_id": request.portal_tenant_id,
                "audience": "trusted_tenant_plus_internal_admin",
                "runtime_flavor": "v2_native",
                "domain": request.portal_domain,
                "deployment_state": "live_state_present" if private_dir.exists() else "not_configured",
                "msn_id": local_msn_id,
            },
            "host_aliases": host_aliases,
            "progeny_links": progeny_links,
            "p2p_contracts": p2p_contracts,
            "external_service_bindings": external_service_bindings,
            "profile_projections": profile_projections,
            "request_log_summary": request_log_summary,
            "local_audit_summary": _local_audit_summary(self._local_audit_file),
            "hosted_manifest_summary": _hosted_manifest_summary(hosted_manifest),
            "warnings": warnings,
        }
        return NetworkRootReadModelResult(source=NetworkRootReadModelSource(payload=payload))
