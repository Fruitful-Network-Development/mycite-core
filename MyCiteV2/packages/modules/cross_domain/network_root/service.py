from __future__ import annotations

from typing import Any

from MyCiteV2.packages.ports.network_root_read_model import (
    NetworkRootReadModelPort,
    NetworkRootReadModelRequest,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _metric(label: str, value: object) -> dict[str, str]:
    return {"label": label, "value": _as_text(value) or "0"}


def _facts(items: list[tuple[str, object]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for label, value in items:
        out.append({"label": label, "value": _as_text(value) or "—"})
    return out


def _entry(label: object, meta: object = "") -> dict[str, str]:
    return {"label": _as_text(label) or "—", "meta": _as_text(meta)}


class NetworkRootReadModelService:
    def __init__(self, read_port: NetworkRootReadModelPort) -> None:
        self._read_port = read_port

    def read_surface(
        self,
        *,
        portal_tenant_id: str,
        portal_domain: object = "",
    ) -> dict[str, Any]:
        result = self._read_port.read_network_root_model(
            NetworkRootReadModelRequest(
                portal_tenant_id=portal_tenant_id,
                portal_domain=portal_domain,
            )
        )
        payload = dict(result.source.payload) if result.source is not None else {}

        portal_instance = dict(payload.get("portal_instance") or {})
        host_aliases = _as_dict_list(payload.get("host_aliases"))
        progeny_links = _as_dict_list(payload.get("progeny_links"))
        p2p_contracts = _as_dict_list(payload.get("p2p_contracts"))
        external_service_bindings = _as_dict_list(payload.get("external_service_bindings"))
        profile_projections = _as_dict_list(payload.get("profile_projections"))
        request_log_summary = dict(payload.get("request_log_summary") or {})
        local_audit_summary = dict(payload.get("local_audit_summary") or {})
        hosted_manifest_summary = dict(payload.get("hosted_manifest_summary") or {})
        warnings = [str(item) for item in list(payload.get("warnings") or []) if _as_text(item)]

        recent_events = _as_dict_list(request_log_summary.get("recent_events"))
        event_types = _as_dict_list(request_log_summary.get("top_event_types"))
        counterparties = _as_dict_list(request_log_summary.get("counterparties"))
        hosted_tabs = [str(item) for item in list(hosted_manifest_summary.get("subject_tabs") or []) if _as_text(item)]

        blocks = [
            {"kind": "metric", "label": "Portal instance", "value": _as_text(portal_instance.get("portal_instance_id")) or portal_tenant_id},
            {"kind": "metric", "label": "Host aliases", "value": str(len(host_aliases))},
            {"kind": "metric", "label": "P2P contracts", "value": str(len(p2p_contracts))},
            {"kind": "metric", "label": "Request log events", "value": str(int(request_log_summary.get("event_count") or 0))},
        ]

        notes = [
            "Network now renders the contract-first entity layer for portal instances, host aliases, progeny links, and P2P contracts.",
            "This root stays read-only: it does not launch a host-alias runtime or provider-owned editor in this pass.",
            "Alias and profile projection remain distinct from provider truth and relationship authority.",
            "Request-log evidence and local audit are summarized together here without collapsing their boundary.",
        ]
        for warning in warnings:
            notes.append(f"Warning: {warning}")

        tab_panels = {
            "messages": {
                "title": "Messages",
                "summary": (
                    f"{int(request_log_summary.get('event_count') or 0)} request-log event(s) across "
                    f"{int(request_log_summary.get('file_count') or 0)} evidence file(s)."
                ),
                "metrics": [
                    _metric("Request log files", request_log_summary.get("file_count") or 0),
                    _metric("Event count", request_log_summary.get("event_count") or 0),
                    _metric("Counterparties", len(counterparties)),
                    _metric("Latest event", request_log_summary.get("latest_event_at") or "—"),
                ],
                "sections": [
                    {
                        "title": "Request-log evidence",
                        "facts": _facts(
                            [
                                ("request_log_dir", request_log_summary.get("request_log_dir")),
                                ("external_event_dir", request_log_summary.get("external_event_dir")),
                                ("latest_event_at", request_log_summary.get("latest_event_at")),
                                ("event_state", request_log_summary.get("state")),
                            ]
                        ),
                    },
                    {
                        "title": "Top event types",
                        "columns": (
                            {"key": "type", "label": "Type"},
                            {"key": "count", "label": "Count"},
                        ),
                        "rows": [
                            {"type": _as_text(row.get("type")) or "unknown", "count": str(int(row.get("count") or 0))}
                            for row in event_types
                        ],
                        "empty_text": "No request-log event types were recorded.",
                    },
                    {
                        "title": "Counterparties",
                        "columns": (
                            {"key": "counterparty", "label": "Counterparty"},
                            {"key": "count", "label": "Events"},
                        ),
                        "rows": [
                            {
                                "counterparty": _as_text(row.get("counterparty")) or "unknown",
                                "count": str(int(row.get("count") or 0)),
                            }
                            for row in counterparties
                        ],
                        "empty_text": "No counterparty evidence is available yet.",
                    },
                    {
                        "title": "Recent evidence",
                        "columns": (
                            {"key": "timestamp", "label": "Timestamp"},
                            {"key": "type", "label": "Type"},
                            {"key": "status", "label": "Status"},
                            {"key": "counterparty", "label": "Counterparty"},
                        ),
                        "rows": [
                            {
                                "timestamp": _as_text(row.get("timestamp")) or "—",
                                "type": _as_text(row.get("type")) or "unknown",
                                "status": _as_text(row.get("status")) or "—",
                                "counterparty": _as_text(row.get("counterparty")) or "—",
                            }
                            for row in recent_events
                        ],
                        "empty_text": "No recent request-log evidence is available.",
                    },
                ],
            },
            "hosted": {
                "title": "Hosted",
                "summary": (
                    f"{_as_text(portal_instance.get('portal_instance_id')) or portal_tenant_id} publishes "
                    f"{len(host_aliases)} host alias(es) and {len(external_service_bindings)} shared binding declaration(s)."
                ),
                "metrics": [
                    _metric("Domain", portal_instance.get("domain") or "—"),
                    _metric("Aliases", len(host_aliases)),
                    _metric("Bindings", len(external_service_bindings)),
                    _metric("Hosted tabs", len(hosted_tabs)),
                ],
                "sections": [
                    {
                        "title": "Portal instance",
                        "facts": _facts(
                            [
                                ("portal_instance_id", portal_instance.get("portal_instance_id")),
                                ("audience", portal_instance.get("audience")),
                                ("runtime_flavor", portal_instance.get("runtime_flavor")),
                                ("domain", portal_instance.get("domain")),
                                ("deployment_state", portal_instance.get("deployment_state")),
                                ("msn_id", portal_instance.get("msn_id")),
                            ]
                        ),
                    },
                    {
                        "title": "Host aliases",
                        "columns": (
                            {"key": "host_alias_id", "label": "Alias"},
                            {"key": "alias_kind", "label": "Kind"},
                            {"key": "projection_state", "label": "State"},
                            {"key": "host_title", "label": "Host"},
                            {"key": "contract_id", "label": "Contract"},
                        ),
                        "rows": [
                            {
                                "host_alias_id": _as_text(row.get("host_alias_id")) or "—",
                                "alias_kind": _as_text(row.get("alias_kind")) or "—",
                                "projection_state": _as_text(row.get("projection_state")) or "—",
                                "host_title": _as_text(row.get("host_title")) or "—",
                                "contract_id": _as_text(row.get("contract_id")) or "—",
                            }
                            for row in host_aliases
                        ],
                        "empty_text": "No host aliases were discovered for this portal instance.",
                    },
                    {
                        "title": "External service bindings",
                        "columns": (
                            {"key": "binding_id", "label": "Binding"},
                            {"key": "binding_family", "label": "Family"},
                            {"key": "provider_kind", "label": "Provider"},
                            {"key": "binding_state", "label": "State"},
                        ),
                        "rows": [
                            {
                                "binding_id": _as_text(row.get("binding_id")) or "—",
                                "binding_family": _as_text(row.get("binding_family")) or "—",
                                "provider_kind": _as_text(row.get("provider_kind")) or "—",
                                "binding_state": _as_text(row.get("binding_state")) or "—",
                            }
                            for row in external_service_bindings
                        ],
                        "empty_text": "No external service bindings were declared for this portal instance.",
                    },
                ],
            },
            "profile": {
                "title": "Profile",
                "summary": (
                    f"{len(profile_projections)} alias or progeny projection(s) with "
                    f"{len(hosted_tabs)} hosted interface tab declaration(s)."
                ),
                "metrics": [
                    _metric("Projection count", len(profile_projections)),
                    _metric("Hosted tabs", len(hosted_tabs)),
                    _metric("Orientation", hosted_manifest_summary.get("orientation_title") or "—"),
                    _metric("Layout", hosted_manifest_summary.get("layout") or "—"),
                ],
                "sections": [
                    {
                        "title": "Hosted interface projection",
                        "facts": _facts(
                            [
                                ("layout", hosted_manifest_summary.get("layout")),
                                ("hero_title", hosted_manifest_summary.get("orientation_title")),
                                ("default_tab_count", hosted_manifest_summary.get("default_hosted_count")),
                                ("channel_count", hosted_manifest_summary.get("channel_count")),
                            ]
                        ),
                    },
                    {
                        "title": "Hosted tabs",
                        "entries": [
                            _entry(tab_label, "subject tab")
                            for tab_label in hosted_tabs
                        ],
                        "empty_text": "No hosted interface tabs were declared.",
                    },
                    {
                        "title": "Alias and progeny projection",
                        "columns": (
                            {"key": "projection_id", "label": "Projection"},
                            {"key": "projection_kind", "label": "Kind"},
                            {"key": "state", "label": "State"},
                            {"key": "title", "label": "Title"},
                            {"key": "contract_ref", "label": "Contract"},
                        ),
                        "rows": [
                            {
                                "projection_id": _as_text(row.get("projection_id")) or "—",
                                "projection_kind": _as_text(row.get("projection_kind")) or "—",
                                "state": _as_text(row.get("state")) or "—",
                                "title": _as_text(row.get("title")) or "—",
                                "contract_ref": _as_text(row.get("contract_ref")) or "—",
                            }
                            for row in profile_projections
                        ],
                        "empty_text": "No alias or progeny profile projections were discovered.",
                    },
                ],
            },
            "contracts": {
                "title": "Contracts",
                "summary": (
                    f"{len(p2p_contracts)} P2P contract record(s), {len(progeny_links)} progeny link(s), and "
                    f"{int(request_log_summary.get('event_count') or 0)} evidence event(s)."
                ),
                "metrics": [
                    _metric("P2P contracts", len(p2p_contracts)),
                    _metric("Progeny links", len(progeny_links)),
                    _metric("Request-log evidence", request_log_summary.get("event_count") or 0),
                    _metric("Local audit", local_audit_summary.get("state") or "—"),
                ],
                "sections": [
                    {
                        "title": "P2P contracts",
                        "columns": (
                            {"key": "p2p_contract_id", "label": "Contract"},
                            {"key": "relationship_kind", "label": "Relationship"},
                            {"key": "enforcement_state", "label": "State"},
                            {"key": "counterparty_msn_id", "label": "Counterparty"},
                            {"key": "evidence_state", "label": "Evidence"},
                        ),
                        "rows": [
                            {
                                "p2p_contract_id": _as_text(row.get("p2p_contract_id")) or "—",
                                "relationship_kind": _as_text(row.get("relationship_kind")) or "—",
                                "enforcement_state": _as_text(row.get("enforcement_state")) or "—",
                                "counterparty_msn_id": _as_text(row.get("counterparty_msn_id")) or "—",
                                "evidence_state": _as_text(row.get("evidence_state")) or "—",
                            }
                            for row in p2p_contracts
                        ],
                        "empty_text": "No P2P contracts were discovered for this portal instance.",
                    },
                    {
                        "title": "Progeny links",
                        "columns": (
                            {"key": "progeny_link_id", "label": "Link"},
                            {"key": "relationship_kind", "label": "Kind"},
                            {"key": "contract_state", "label": "State"},
                            {"key": "target_portal_instance_id", "label": "Target"},
                        ),
                        "rows": [
                            {
                                "progeny_link_id": _as_text(row.get("progeny_link_id")) or "—",
                                "relationship_kind": _as_text(row.get("relationship_kind")) or "—",
                                "contract_state": _as_text(row.get("contract_state")) or "—",
                                "target_portal_instance_id": _as_text(row.get("target_portal_instance_id")) or "—",
                            }
                            for row in progeny_links
                        ],
                        "empty_text": "No progeny links were discovered for this portal instance.",
                    },
                    {
                        "title": "Evidence boundary",
                        "facts": _facts(
                            [
                                ("request_log_dir", request_log_summary.get("request_log_dir")),
                                ("request_log_events", request_log_summary.get("event_count")),
                                ("local_audit_path", local_audit_summary.get("path")),
                                ("local_audit_state", local_audit_summary.get("state")),
                                ("local_audit_records", local_audit_summary.get("line_count")),
                            ]
                        ),
                    },
                ],
            },
        }

        return {
            "network_state": "contract_first_read_model",
            "portal_instance": portal_instance,
            "summary": {
                "hosted_root": "contract_first_read_model",
                "portal_instance_id": _as_text(portal_instance.get("portal_instance_id")) or portal_tenant_id,
                "domain": _as_text(portal_instance.get("domain")),
                "host_alias_count": len(host_aliases),
                "progeny_link_count": len(progeny_links),
                "contract_count": len(p2p_contracts),
                "request_log_event_count": int(request_log_summary.get("event_count") or 0),
                "local_audit_state": _as_text(local_audit_summary.get("state")) or "not_configured",
                "visible_utility_count": 0,
            },
            "blocks": blocks,
            "notes": notes,
            "tab_panels": tab_panels,
        }
