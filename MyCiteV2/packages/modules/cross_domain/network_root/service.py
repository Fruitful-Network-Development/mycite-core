from __future__ import annotations

from typing import Any

from MyCiteV2.packages.modules.shared import as_dict_list, as_text
from MyCiteV2.packages.ports.network_root_read_model import (
    NetworkRootReadModelPort,
    NetworkRootReadModelRequest,
)


def _metric(label: str, value: object, *, meta: object = "") -> dict[str, str]:
    return {
        "label": as_text(label),
        "value": as_text(value) or "0",
        "meta": as_text(meta),
    }


class NetworkRootReadModelService:
    def __init__(self, read_port: NetworkRootReadModelPort) -> None:
        self._read_port = read_port

    def read_surface(
        self,
        *,
        portal_tenant_id: str,
        portal_domain: object = "",
        surface_query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = self._read_port.read_network_root_model(
            NetworkRootReadModelRequest(
                portal_tenant_id=portal_tenant_id,
                portal_domain=portal_domain,
                surface_query=surface_query,
            )
        )
        payload = dict(result.source.payload) if result.source is not None else {}
        portal_instance = dict(payload.get("portal_instance") or {})
        workspace = dict(payload.get("system_log_workbench") or {})
        warnings = [str(item) for item in list(payload.get("warnings") or []) if as_text(item)]
        records = as_dict_list(workspace.get("records"))
        event_type_filters = as_dict_list(workspace.get("event_type_filters"))
        contract_filters = as_dict_list(workspace.get("contract_filters"))
        summary = dict(workspace.get("summary") or {})
        active_filters = dict(workspace.get("active_filters") or {})
        selected_record = dict(workspace.get("selected_record") or {}) if isinstance(workspace.get("selected_record"), dict) else None
        selected_contract = dict(workspace.get("selected_contract") or {}) if isinstance(workspace.get("selected_contract"), dict) else None
        chronology = dict(workspace.get("chronology") or {})
        audit_summary = dict(workspace.get("audit_summary") or {})

        cards = [
            _metric("Portal instance", portal_instance.get("portal_instance_id") or portal_tenant_id),
            _metric("System log records", summary.get("record_count") or 0),
            _metric("Event types", summary.get("event_type_count") or 0),
            _metric("Contracts", summary.get("contract_count") or 0),
        ]

        notes = [
            "NETWORK is the portal-instance system-log workbench.",
            "This root is read-only, non-reducer-owned, and does not host tool or sandbox runtime behavior.",
            "Contract correspondence is selected as a filter over the same canonical system-log document.",
        ]
        for warning in warnings:
            notes.append(f"Warning: {warning}")

        return {
            "kind": "network_system_log_workspace",
            "title": "Network",
            "subtitle": "Portal-instance system-log workbench.",
            "cards": cards,
            "notes": notes,
            "workspace": {
                "state": as_text(workspace.get("state")) or "empty",
                "document_path": as_text(workspace.get("document_path")),
                "active_filters": {
                    "view": as_text(active_filters.get("view")) or "system_logs",
                    "contract_id": as_text(active_filters.get("contract_id")),
                    "event_type_id": as_text(active_filters.get("event_type_id")),
                    "record_id": as_text(active_filters.get("record_id")),
                },
                "summary": {
                    "record_count": int(summary.get("record_count") or 0),
                    "event_type_count": int(summary.get("event_type_count") or 0),
                    "contract_count": int(summary.get("contract_count") or 0),
                    "latest_hops_timestamp": as_text(summary.get("latest_hops_timestamp")),
                },
                "chronology": chronology,
                "audit_summary": audit_summary,
                "event_type_filters": event_type_filters,
                "contract_filters": contract_filters,
                "records": [
                    {
                        "datum_address": as_text(record.get("datum_address")),
                        "title": as_text(record.get("title") or record.get("label")),
                        "label": as_text(record.get("label") or record.get("title")),
                        "hops_timestamp": as_text(record.get("hops_timestamp")),
                        "event_type_id": as_text(record.get("event_type_id")),
                        "event_type_label": as_text(record.get("event_type_label") or record.get("event_type_slug")),
                        "status": as_text(record.get("status")),
                        "counterparty": as_text(record.get("counterparty")),
                        "contract_id": as_text(record.get("contract_id")),
                        "selected": as_text(record.get("datum_address")) == as_text(active_filters.get("record_id")),
                    }
                    for record in records
                ],
                "selected_record": selected_record,
                "selected_contract": selected_contract,
                "empty_text": "No canonical system-log rows are available for the current filters.",
            },
        }
