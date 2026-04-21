from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from MyCiteV2.packages.adapters.sql import SqliteDirectiveContextAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql.datum_semantics import datum_address_sort_key, parse_datum_address
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocument, AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.ports.directive_context import DirectiveContextEventQuery, DirectiveContextRequest

WORKBENCH_UI_TOOL_ID = "workbench_ui"
WORKBENCH_UI_DEFAULT_SORT = "datum_address"
_SORT_KEYS = {
    "datum_address",
    "layer",
    "value_group",
    "iteration",
    "labels",
    "relation",
    "object_ref",
    "hyphae_hash",
}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _joined_labels(raw: Any) -> str:
    if isinstance(raw, list) and len(raw) > 1 and isinstance(raw[1], (list, tuple)):
        return ", ".join(_as_text(item) for item in raw[1] if _as_text(item))
    if isinstance(raw, dict):
        labels = raw.get("labels") or raw.get("label") or raw.get("name") or ()
        if isinstance(labels, (list, tuple)):
            return ", ".join(_as_text(item) for item in labels if _as_text(item))
        return _as_text(labels)
    return ""


def _relation(raw: Any) -> str:
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        triple = raw[0]
        return _as_text(triple[1] if len(triple) > 1 else "")
    if isinstance(raw, dict):
        return _as_text(raw.get("relation") or raw.get("predicate"))
    return ""


def _object_ref(raw: Any, *, datum_address: str) -> str:
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        triple = raw[0]
        return _as_text(triple[2] if len(triple) > 2 else "")
    if isinstance(raw, dict):
        return _as_text(raw.get("object_ref") or raw.get("object") or datum_address)
    return ""


def _row_filter_haystack(row: dict[str, Any]) -> str:
    return " ".join(
        _as_text(row.get(key)).lower()
        for key in ("datum_address", "labels", "relation", "object_ref", "hyphae_hash")
    )


def _row_sort_value(row: dict[str, Any], *, sort_key: str) -> Any:
    if sort_key == "datum_address":
        return datum_address_sort_key(row["datum_address"])
    if sort_key in {"layer", "value_group", "iteration"}:
        return int(row.get(sort_key) or 0)
    return _as_text(row.get(sort_key)).lower()


def _overlay_summary_rows(overlay: dict[str, Any] | None, *, event_rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    rows = [
        {"label": "overlay", "value": "loaded" if overlay is not None else "missing"},
        {"label": "context id", "value": _as_text((overlay or {}).get("context_id")) or "—"},
        {"label": "subject version hash", "value": _as_text((overlay or {}).get("subject_version_hash")) or "—"},
        {"label": "subject hyphae hash", "value": _as_text((overlay or {}).get("subject_hyphae_hash")) or "—"},
    ]
    if overlay is not None:
        rows.append(
            {
                "label": "NIMM",
                "value": json.dumps(dict(overlay.get("nimm_state") or {}), sort_keys=True),
            }
        )
        rows.append(
            {
                "label": "AITAS",
                "value": json.dumps(dict(overlay.get("aitas_state") or {}), sort_keys=True),
            }
        )
    event_rows = list(event_rows)
    if event_rows:
        rows.append({"label": "recent events", "value": str(len(event_rows))})
    return rows


class WorkbenchUiReadService:
    def __init__(self, db_file: str | Path) -> None:
        self._db_file = Path(db_file)
        self._datum_store = SqliteSystemDatumStoreAdapter(self._db_file)
        self._directive_context = SqliteDirectiveContextAdapter(self._db_file)

    def _document_rows(
        self,
        *,
        tenant_id: str,
        document: AuthoritativeDatumDocument,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in sorted(document.rows, key=lambda item: datum_address_sort_key(item.datum_address)):
            layer, value_group, iteration = parse_datum_address(row.datum_address)
            semantics = self._datum_store.read_datum_semantic_identity(
                tenant_id=tenant_id,
                document_id=document.document_id,
                datum_address=row.datum_address,
            )
            items.append(
                {
                    "datum_address": row.datum_address,
                    "layer": layer,
                    "value_group": value_group,
                    "iteration": iteration,
                    "labels": _joined_labels(row.raw),
                    "relation": _relation(row.raw),
                    "object_ref": _object_ref(row.raw, datum_address=row.datum_address),
                    "hyphae_hash": _as_text((semantics or {}).get("hyphae_hash")),
                    "semantic_hash": _as_text((semantics or {}).get("semantic_hash")),
                    "warnings": list((semantics or {}).get("warnings") or []),
                    "raw": row.raw,
                }
            )
        return items

    def read_surface(
        self,
        *,
        portal_instance_id: str,
        portal_domain: str,
        surface_query: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        del portal_domain
        query = dict(surface_query or {})
        catalog = self._datum_store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=portal_instance_id)
        )
        selected_document_id = _as_text(query.get("document"))
        selected_row_id = _as_text(query.get("row"))
        text_filter = _as_text(query.get("filter")).lower()
        sort_key = _as_text(query.get("sort")).lower() or WORKBENCH_UI_DEFAULT_SORT
        if sort_key not in _SORT_KEYS:
            sort_key = WORKBENCH_UI_DEFAULT_SORT
        sort_direction = "desc" if _as_text(query.get("dir")).lower() == "desc" else "asc"
        overlay_visibility = "hide" if _as_text(query.get("overlay")).lower() == "hide" else "show"

        documents = list(catalog.documents)
        if not selected_document_id and documents:
            selected_document_id = documents[0].document_id
        active_document = next((document for document in documents if document.document_id == selected_document_id), None)
        if active_document is None and documents:
            active_document = documents[0]
            selected_document_id = active_document.document_id

        document_identity = None
        rows: list[dict[str, Any]] = []
        if active_document is not None:
            document_identity = self._datum_store.read_document_version_identity(
                tenant_id=portal_instance_id,
                document_id=active_document.document_id,
            )
            rows = self._document_rows(tenant_id=portal_instance_id, document=active_document)
        if text_filter:
            rows = [row for row in rows if text_filter in _row_filter_haystack(row)]
        rows.sort(key=lambda row: (_row_sort_value(row, sort_key=sort_key), row["datum_address"]), reverse=sort_direction == "desc")
        selected_row = next((row for row in rows if row["datum_address"] == selected_row_id), None)
        if selected_row is None and rows:
            selected_row = rows[0]
            selected_row_id = selected_row["datum_address"]

        overlay = None
        overlay_events: list[dict[str, Any]] = []
        if overlay_visibility == "show" and document_identity is not None:
            request = DirectiveContextRequest(
                portal_instance_id=portal_instance_id,
                tool_id=WORKBENCH_UI_TOOL_ID,
                subject_hyphae_hash=_as_text((selected_row or {}).get("hyphae_hash")),
                subject_version_hash=_as_text(document_identity.get("version_hash")),
            )
            directive_result = self._directive_context.read_directive_context(request)
            if directive_result.source is not None:
                overlay = directive_result.source.to_dict()
                overlay_events = [
                    record.to_dict()
                    for record in self._directive_context.read_directive_context_events(
                        DirectiveContextEventQuery(
                            portal_instance_id=portal_instance_id,
                            tool_id=WORKBENCH_UI_TOOL_ID,
                            context_id=directive_result.source.context_id,
                            limit=5,
                        )
                    )
                ]

        document_rows = [
            {
                "document_id": document.document_id,
                "label": document.document_name,
                "source_kind": document.source_kind,
                "row_count": str(document.row_count),
                "selected": document.document_id == selected_document_id,
            }
            for document in documents
        ]

        return {
            "tool_id": WORKBENCH_UI_TOOL_ID,
            "document_id": selected_document_id,
            "document_rows": document_rows,
            "document_version_hash": _as_text((document_identity or {}).get("version_hash")),
            "row_count": len(rows),
            "sort_key": sort_key,
            "sort_direction": sort_direction,
            "text_filter": text_filter,
            "overlay_visibility": overlay_visibility,
            "rows": rows,
            "selected_row": selected_row,
            "overlay": overlay,
            "overlay_events": overlay_events,
            "warnings": list(catalog.warnings),
            "surface_payload": {
                "kind": "workbench_ui_surface",
                "tool_id": WORKBENCH_UI_TOOL_ID,
                "title": "Workbench UI",
                "subtitle": "Read-only SQL-backed datum grid with additive directive overlays.",
                "cards": [
                    {"label": "document", "value": selected_document_id or "—"},
                    {"label": "version hash", "value": _as_text((document_identity or {}).get("version_hash")) or "—"},
                    {"label": "rows", "value": str(len(rows))},
                    {"label": "overlay", "value": overlay_visibility},
                ],
                "sections": [
                    {
                        "title": "Datum Grid",
                        "summary": "Spreadsheet-like read-only rows backed by MOS SQL authority.",
                        "columns": [
                            {"key": "datum_address", "label": "datum_address"},
                            {"key": "layer", "label": "layer"},
                            {"key": "value_group", "label": "value_group"},
                            {"key": "iteration", "label": "iteration"},
                            {"key": "labels", "label": "labels"},
                            {"key": "relation", "label": "relation"},
                            {"key": "object_ref", "label": "object_ref"},
                            {"key": "hyphae_hash", "label": "hyphae_hash"},
                        ],
                        "items": rows,
                    },
                    {
                        "title": "Query Controls",
                        "rows": [
                            {"label": "filter", "value": text_filter or "—"},
                            {"label": "sort", "value": sort_key},
                            {"label": "direction", "value": sort_direction},
                            {"label": "overlay visibility", "value": overlay_visibility},
                        ],
                    },
                ],
                "notes": [
                    "Directive overlays are additive summaries only.",
                    "No mutation controls are exposed on this surface.",
                ],
            },
            "inspector_sections": [
                {
                    "title": "Selection",
                    "rows": [
                        {"label": "document id", "value": selected_document_id or "—"},
                        {"label": "datum address", "value": _as_text((selected_row or {}).get("datum_address")) or "—"},
                        {"label": "semantic hash", "value": _as_text((selected_row or {}).get("semantic_hash")) or "—"},
                        {"label": "hyphae hash", "value": _as_text((selected_row or {}).get("hyphae_hash")) or "—"},
                        {
                            "label": "raw",
                            "value": json.dumps((selected_row or {}).get("raw"), sort_keys=True),
                        },
                    ],
                },
                {
                    "title": "Directive Overlay",
                    "rows": _overlay_summary_rows(overlay, event_rows=overlay_events),
                },
            ],
        }
