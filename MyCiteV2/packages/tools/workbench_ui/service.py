from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from MyCiteV2.packages.adapters.sql import SqliteDirectiveContextAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql.datum_semantics import datum_address_sort_key, parse_datum_address
from MyCiteV2.packages.modules.domains.datum_recognition import recognize_authoritative_document
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocument, AuthoritativeDatumDocumentRequest
from MyCiteV2.packages.ports.directive_context import DirectiveContextEventQuery, DirectiveContextRequest
from MyCiteV2.packages.state_machine.lens import resolve_datum_lens

WORKBENCH_UI_TOOL_ID = "workbench_ui"
WORKBENCH_UI_DEFAULT_DOCUMENT_SORT = "version_hash"
WORKBENCH_UI_DEFAULT_ROW_SORT = "datum_address"
WORKBENCH_UI_DEFAULT_GROUP = "flat"
WORKBENCH_UI_DEFAULT_LENS = "interpreted"
WORKBENCH_UI_DEFAULT_SOURCE_VISIBILITY = "show"
WORKBENCH_UI_DEFAULT_OVERLAY_VISIBILITY = "show"
WORKBENCH_UI_PREFERRED_DOCUMENT_PREFIX = "sandbox:cts_gis:"

_DOCUMENT_SORT_KEYS = {
    "document_id",
    "document_name",
    "source_kind",
    "row_count",
    "version_hash",
}
_ROW_SORT_KEYS = {
    "datum_address",
    "layer",
    "value_group",
    "iteration",
    "labels",
    "relation",
    "object_ref",
    "hyphae_hash",
}
_GROUP_MODES = {"flat", "layer", "layer_value_group", "layer_value_group_iteration"}
_LENS_MODES = {"interpreted", "raw"}
_VISIBILITY_MODES = {"show", "hide"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_sort_key(value: object, *, allowed: set[str], default: str) -> str:
    sort_key = _as_text(value).lower() or default
    if sort_key not in allowed:
        return default
    return sort_key


def _normalize_sort_direction(value: object) -> str:
    return "desc" if _as_text(value).lower() == "desc" else "asc"


def _normalize_mode(value: object, *, allowed: set[str], default: str) -> str:
    token = _as_text(value).lower() or default
    if token not in allowed:
        return default
    return token


def _short_hash(value: object, *, length: int = 12) -> str:
    token = _as_text(value)
    return token[:length] if token else ""


def _truncate_text(value: object, *, limit: int = 96) -> str:
    token = _as_text(value)
    if len(token) <= limit:
        return token
    return f"{token[:limit - 1]}…"


def _json_text(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return _as_text(value)


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


def _document_filter_haystack(document: dict[str, Any]) -> str:
    return " ".join(
        _as_text(document.get(key)).lower()
        for key in ("document_id", "document_name", "source_kind", "version_hash")
    )


def _document_sort_value(document: dict[str, Any], *, sort_key: str) -> Any:
    if sort_key == "row_count":
        return int(document.get(sort_key) or 0)
    return _as_text(document.get(sort_key)).lower()


def _row_filter_haystack(row: dict[str, Any]) -> str:
    return " ".join(
        _as_text(row.get(key)).lower()
        for key in (
            "datum_address",
            "labels",
            "relation",
            "object_ref",
            "hyphae_hash",
            "semantic_hash",
            "raw_json",
            "display_value",
            "recognized_family",
            "resolved_lens",
        )
    )


def _row_sort_value(row: dict[str, Any], *, sort_key: str) -> Any:
    if sort_key == "datum_address":
        return datum_address_sort_key(row["datum_address"])
    if sort_key in {"layer", "value_group", "iteration"}:
        return int(row.get(sort_key) or 0)
    return _as_text(row.get(sort_key)).lower()


def _joined_tokens(values: object) -> str:
    if not isinstance(values, (list, tuple)):
        return _as_text(values)
    return ", ".join(_as_text(item) for item in values if _as_text(item))


def _first_non_empty(*values: object) -> str:
    for value in values:
        token = _as_text(value)
        if token:
            return token
    return ""


def _display_summary(*, relation: str, object_ref: str, recognized_family: str, resolved_lens: str, diagnostics: tuple[str, ...]) -> str:
    bits = [
        recognized_family,
        f"lens:{resolved_lens}" if resolved_lens else "",
        f"{relation} -> {object_ref}" if relation or object_ref else "",
        _joined_tokens(diagnostics),
    ]
    return " · ".join(bit for bit in bits if bit)


def _layer_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    layers: dict[int, dict[str, Any]] = {}
    value_groups: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        layer = int(row.get("layer") or 0)
        value_group = int(row.get("value_group") or 0)
        layer_entry = layers.setdefault(
            layer,
            {
                "layer": layer,
                "title": f"Layer {layer}",
                "summary": f"Iteration cells grouped under layer {layer}.",
                "value_groups": [],
                "row_count": 0,
                "selected": False,
            },
        )
        value_group_entry = value_groups.setdefault(
            (layer, value_group),
            {
                "value_group": value_group,
                "title": f"Value Group {value_group}",
                "summary": f"Iteration cells for value group {value_group}.",
                "cells": [],
                "row_count": 0,
                "selected": False,
            },
        )
        if value_group_entry not in layer_entry["value_groups"]:
            layer_entry["value_groups"].append(value_group_entry)
        value_group_entry["cells"].append(row)
        value_group_entry["row_count"] += 1
        value_group_entry["selected"] = value_group_entry["selected"] or bool(row.get("selected"))
        layer_entry["row_count"] += 1
        layer_entry["selected"] = layer_entry["selected"] or bool(row.get("selected"))
    ordered_layers = [layers[key] for key in sorted(layers)]
    for layer_entry in ordered_layers:
        groups = sorted(
            list(layer_entry["value_groups"]),
            key=lambda item: int(item.get("value_group") or 0),
        )
        for group in groups:
            group["cells"] = sorted(
                list(group["cells"]),
                key=lambda item: datum_address_sort_key(item["datum_address"]),
            )
        layer_entry["value_groups"] = groups
    return ordered_layers


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


def _document_table_columns(*, source_visibility: str) -> list[dict[str, str]]:
    columns = [
        {"key": "document_name", "label": "document_name"},
        {"key": "document_id", "label": "document_id"},
    ]
    if source_visibility == "show":
        columns.append({"key": "source_kind", "label": "source_kind"})
    columns.extend(
        [
            {"key": "version_hash_short", "label": "version_hash_badge"},
            {"key": "version_hash", "label": "version_hash"},
            {"key": "row_count", "label": "row_count"},
        ]
    )
    return columns


def _datum_grid_columns(*, workbench_lens: str) -> list[dict[str, str]]:
    columns = [
        {"key": "datum_address", "label": "datum_address"},
        {"key": "layer", "label": "layer"},
        {"key": "value_group", "label": "value_group"},
        {"key": "iteration", "label": "iteration"},
    ]
    if workbench_lens == "raw":
        columns.extend(
            [
                {"key": "raw_preview", "label": "raw"},
                {"key": "hyphae_hash_short", "label": "hyphae_hash_badge"},
            ]
        )
    else:
        columns.extend(
            [
                {"key": "labels", "label": "labels"},
                {"key": "relation", "label": "relation"},
                {"key": "object_ref", "label": "object_ref"},
                {"key": "hyphae_hash_short", "label": "hyphae_hash_badge"},
            ]
        )
    return columns


def _group_rows(rows: list[dict[str, Any]], *, group_mode: str, workbench_lens: str) -> list[dict[str, Any]]:
    if group_mode == "flat":
        return [
            {
                "key": "flat",
                "title": "All Rows",
                "summary": "Flat row list for the selected authoritative document.",
                "columns": _datum_grid_columns(workbench_lens=workbench_lens),
                "items": rows,
                "row_count": len(rows),
            }
        ]

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if group_mode == "layer":
            key = f"layer:{row['layer']}"
            title = f"Layer {row['layer']}"
            summary = f"Canonical datum order within layer {row['layer']}."
        else:
            key = f"layer:{row['layer']}:value_group:{row['value_group']}"
            title = f"Layer {row['layer']} / Value Group {row['value_group']}"
            summary = (
                f"Canonical datum order within layer {row['layer']} "
                f"and value group {row['value_group']}."
            )
        grouped.setdefault(
            key,
            {
                "key": key,
                "title": title,
                "summary": summary,
                "columns": _datum_grid_columns(workbench_lens=workbench_lens),
                "items": [],
            },
        )["items"].append(row)

    groups = list(grouped.values())
    for group in groups:
        items = list(group["items"])
        items.sort(key=lambda item: datum_address_sort_key(item["datum_address"]))
        group["items"] = items
        group["row_count"] = len(items)
    groups.sort(key=lambda group: datum_address_sort_key(group["items"][0]["datum_address"]) if group["items"] else ())
    return groups


def _section_rows_for_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for group in groups:
        sections.append(
            {
                "title": group["title"],
                "summary": group["summary"],
                "columns": list(group["columns"]),
                "items": list(group["items"]),
            }
        )
    return sections


def _navigation_item(items: list[dict[str, Any]], *, index: int, label_key: str, id_key: str) -> dict[str, str] | None:
    if index < 0 or index >= len(items):
        return None
    item = items[index]
    return {
        "id": _as_text(item.get(id_key)),
        "label": _as_text(item.get(label_key)) or _as_text(item.get(id_key)) or "—",
    }


def _preferred_document_id(document_rows: list[dict[str, Any]]) -> str:
    for document in document_rows:
        document_id = _as_text(document.get("document_id"))
        if document_id.startswith(WORKBENCH_UI_PREFERRED_DOCUMENT_PREFIX):
            return document_id
    return _as_text((document_rows[0] if document_rows else {}).get("document_id"))


class WorkbenchUiReadService:
    def __init__(self, db_file: str | Path) -> None:
        self._db_file = Path(db_file)
        self._datum_store = SqliteSystemDatumStoreAdapter(self._db_file)
        self._directive_context = SqliteDirectiveContextAdapter(self._db_file)

    def _build_document_entry(
        self,
        *,
        tenant_id: str,
        document: AuthoritativeDatumDocument,
    ) -> dict[str, Any]:
        document_identity = self._datum_store.read_document_version_identity(
            tenant_id=tenant_id,
            document_id=document.document_id,
        )
        version_hash = _as_text((document_identity or {}).get("version_hash"))
        return {
            "document_id": document.document_id,
            "document_name": document.document_name,
            "label": document.document_name,
            "source_kind": document.source_kind,
            "row_count": int(document.row_count),
            "version_hash": version_hash,
            "version_hash_short": _short_hash(version_hash),
            "selected": False,
        }

    def _row_items(
        self,
        *,
        tenant_id: str,
        document: AuthoritativeDatumDocument,
    ) -> list[dict[str, Any]]:
        recognized_document = recognize_authoritative_document(document)
        recognized_rows = {
            row.datum_address: row
            for row in recognized_document.rows
        }
        items: list[dict[str, Any]] = []
        for row in sorted(document.rows, key=lambda item: datum_address_sort_key(item.datum_address)):
            layer, value_group, iteration = parse_datum_address(row.datum_address)
            semantics = self._datum_store.read_datum_semantic_identity(
                tenant_id=tenant_id,
                document_id=document.document_id,
                datum_address=row.datum_address,
            )
            recognized = recognized_rows.get(row.datum_address)
            hyphae_hash = _as_text((semantics or {}).get("hyphae_hash"))
            semantic_hash = _as_text((semantics or {}).get("semantic_hash"))
            recognized_family = _as_text(getattr(recognized, "recognized_family", ""))
            recognized_anchor = _as_text(getattr(recognized, "recognized_anchor", ""))
            primary_value_token = _as_text(getattr(recognized, "primary_value_token", ""))
            render_hints = dict(getattr(recognized, "render_hints", {}) or {})
            diagnostics = tuple(getattr(recognized, "diagnostic_states", ()) or ())
            lens_resolution = resolve_datum_lens(
                recognized_family=recognized_family,
                primary_value_kind=render_hints.get("primary_value_kind"),
                overlay_kind=render_hints.get("overlay_kind"),
            )
            display_value = _first_non_empty(
                lens_resolution.lens.decode(primary_value_token) if primary_value_token else "",
                _joined_labels(row.raw),
                _object_ref(row.raw, datum_address=row.datum_address),
            )
            raw_json = _json_text(row.raw)
            hyphae_chain = dict((semantics or {}).get("hyphae_chain") or {})
            hyphae_chain_addresses = list(hyphae_chain.get("addresses") or [])
            local_references = list((semantics or {}).get("local_references") or [])
            items.append(
                {
                    "datum_address": row.datum_address,
                    "layer": layer,
                    "value_group": value_group,
                    "iteration": iteration,
                    "labels": _joined_labels(row.raw),
                    "relation": _relation(row.raw),
                    "object_ref": _object_ref(row.raw, datum_address=row.datum_address),
                    "recognized_family": recognized_family,
                    "recognized_anchor": recognized_anchor,
                    "primary_value_token": primary_value_token,
                    "primary_value_kind": _as_text(render_hints.get("primary_value_kind")),
                    "overlay_kind": _as_text(render_hints.get("overlay_kind")),
                    "diagnostic_states": list(diagnostics),
                    "resolved_lens": lens_resolution.lens_id,
                    "resolved_lens_match": lens_resolution.matched_on,
                    "display_value": display_value,
                    "display_summary": _display_summary(
                        relation=_relation(row.raw),
                        object_ref=_object_ref(row.raw, datum_address=row.datum_address),
                        recognized_family=recognized_family,
                        resolved_lens=lens_resolution.lens_id,
                        diagnostics=diagnostics,
                    ),
                    "hyphae_hash": hyphae_hash,
                    "hyphae_hash_short": _short_hash(hyphae_hash),
                    "semantic_hash": semantic_hash,
                    "semantic_hash_short": _short_hash(semantic_hash),
                    "hyphae_policy": _as_text((semantics or {}).get("policy")),
                    "hyphae_chain_addresses": hyphae_chain_addresses,
                    "hyphae_chain_length": len(hyphae_chain_addresses),
                    "local_references": local_references,
                    "local_reference_count": len(local_references),
                    "warnings": list((semantics or {}).get("warnings") or []),
                    "raw": row.raw,
                    "raw_json": raw_json,
                    "raw_preview": _truncate_text(raw_json),
                    "selected": False,
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
        document_filter = _as_text(query.get("document_filter")).lower()
        document_sort_key = _normalize_sort_key(
            query.get("document_sort"),
            allowed=_DOCUMENT_SORT_KEYS,
            default=WORKBENCH_UI_DEFAULT_DOCUMENT_SORT,
        )
        document_sort_direction = _normalize_sort_direction(query.get("document_dir"))
        text_filter = _as_text(query.get("filter")).lower()
        row_sort_key = _normalize_sort_key(query.get("sort"), allowed=_ROW_SORT_KEYS, default=WORKBENCH_UI_DEFAULT_ROW_SORT)
        row_sort_direction = _normalize_sort_direction(query.get("dir"))
        group_mode = _normalize_mode(query.get("group"), allowed=_GROUP_MODES, default=WORKBENCH_UI_DEFAULT_GROUP)
        workbench_lens = _normalize_mode(query.get("workbench_lens"), allowed=_LENS_MODES, default=WORKBENCH_UI_DEFAULT_LENS)
        source_visibility = _normalize_mode(
            query.get("source"),
            allowed=_VISIBILITY_MODES,
            default=WORKBENCH_UI_DEFAULT_SOURCE_VISIBILITY,
        )
        overlay_visibility = _normalize_mode(
            query.get("overlay"),
            allowed=_VISIBILITY_MODES,
            default=WORKBENCH_UI_DEFAULT_OVERLAY_VISIBILITY,
        )

        documents = list(catalog.documents)
        document_rows = [
            self._build_document_entry(tenant_id=portal_instance_id, document=document)
            for document in documents
        ]
        if document_filter:
            document_rows = [document for document in document_rows if document_filter in _document_filter_haystack(document)]
        document_rows.sort(
            key=lambda document: (
                _document_sort_value(document, sort_key=document_sort_key),
                _as_text(document.get("document_id")).lower(),
            ),
            reverse=document_sort_direction == "desc",
        )
        if selected_document_id not in {document["document_id"] for document in document_rows}:
            selected_document_id = ""
        if not selected_document_id and document_rows:
            selected_document_id = _preferred_document_id(document_rows)

        active_document = next((document for document in documents if document.document_id == selected_document_id), None)
        active_document_row = next((document for document in document_rows if document["document_id"] == selected_document_id), None)
        for document in document_rows:
            document["selected"] = document["document_id"] == selected_document_id

        document_version_hash = _as_text((active_document_row or {}).get("version_hash"))
        document_version_hash_short = _as_text((active_document_row or {}).get("version_hash_short"))
        rows: list[dict[str, Any]] = []
        if active_document is not None:
            rows = self._row_items(tenant_id=portal_instance_id, document=active_document)
        if text_filter:
            rows = [row for row in rows if text_filter in _row_filter_haystack(row)]

        flat_rows = list(rows)
        flat_rows.sort(
            key=lambda row: (_row_sort_value(row, sort_key=row_sort_key), row["datum_address"]),
            reverse=row_sort_direction == "desc",
        )
        grouped_rows = list(rows)
        grouped_rows.sort(key=lambda row: datum_address_sort_key(row["datum_address"]))
        active_rows = flat_rows if group_mode == "flat" else grouped_rows

        selected_row = next((row for row in active_rows if row["datum_address"] == selected_row_id), None)
        if selected_row is None and active_rows:
            selected_row = active_rows[0]
        selected_row_id = _as_text((selected_row or {}).get("datum_address"))
        for row in rows:
            row["selected"] = row["datum_address"] == selected_row_id
        selected_row = next((row for row in rows if row["datum_address"] == selected_row_id), selected_row)

        row_groups = _group_rows(grouped_rows, group_mode=group_mode, workbench_lens=workbench_lens)
        layer_matrix = _layer_matrix(grouped_rows)
        row_sections = _section_rows_for_groups(row_groups)
        visible_row_items = flat_rows if group_mode == "flat" else []

        overlay = None
        overlay_events: list[dict[str, Any]] = []
        if overlay_visibility == "show" and document_version_hash:
            request = DirectiveContextRequest(
                portal_instance_id=portal_instance_id,
                tool_id=WORKBENCH_UI_TOOL_ID,
                subject_hyphae_hash=_as_text((selected_row or {}).get("hyphae_hash")),
                subject_version_hash=document_version_hash,
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

        document_index = next(
            (index for index, document in enumerate(document_rows) if document["document_id"] == selected_document_id),
            -1,
        )
        row_index = next(
            (index for index, row in enumerate(active_rows) if row["datum_address"] == selected_row_id),
            -1,
        )
        navigation = {
            "previous_document": _navigation_item(document_rows, index=document_index - 1, label_key="document_name", id_key="document_id"),
            "next_document": _navigation_item(document_rows, index=document_index + 1, label_key="document_name", id_key="document_id"),
            "previous_row": _navigation_item(active_rows, index=row_index - 1, label_key="datum_address", id_key="datum_address"),
            "next_row": _navigation_item(active_rows, index=row_index + 1, label_key="datum_address", id_key="datum_address"),
        }

        selected_document_summary = {
            "document_id": selected_document_id,
            "document_name": _as_text((active_document_row or {}).get("document_name")),
            "source_kind": _as_text((active_document_row or {}).get("source_kind")),
            "version_hash": document_version_hash,
            "version_hash_short": document_version_hash_short,
            "row_count": int((active_document_row or {}).get("row_count") or 0),
        }
        selected_row_summary = {
            "datum_address": _as_text((selected_row or {}).get("datum_address")),
            "layer": int((selected_row or {}).get("layer") or 0),
            "value_group": int((selected_row or {}).get("value_group") or 0),
            "iteration": int((selected_row or {}).get("iteration") or 0),
            "labels": _as_text((selected_row or {}).get("labels")),
            "relation": _as_text((selected_row or {}).get("relation")),
            "object_ref": _as_text((selected_row or {}).get("object_ref")),
            "recognized_family": _as_text((selected_row or {}).get("recognized_family")),
            "recognized_anchor": _as_text((selected_row or {}).get("recognized_anchor")),
            "primary_value_token": _as_text((selected_row or {}).get("primary_value_token")),
            "primary_value_kind": _as_text((selected_row or {}).get("primary_value_kind")),
            "overlay_kind": _as_text((selected_row or {}).get("overlay_kind")),
            "resolved_lens": _as_text((selected_row or {}).get("resolved_lens")),
            "resolved_lens_match": _as_text((selected_row or {}).get("resolved_lens_match")),
            "display_value": _as_text((selected_row or {}).get("display_value")),
            "display_summary": _as_text((selected_row or {}).get("display_summary")),
            "diagnostic_states": list((selected_row or {}).get("diagnostic_states") or []),
            "hyphae_hash": _as_text((selected_row or {}).get("hyphae_hash")),
            "hyphae_hash_short": _as_text((selected_row or {}).get("hyphae_hash_short")),
            "semantic_hash": _as_text((selected_row or {}).get("semantic_hash")),
            "semantic_hash_short": _as_text((selected_row or {}).get("semantic_hash_short")),
            "hyphae_policy": _as_text((selected_row or {}).get("hyphae_policy")),
            "hyphae_chain_addresses": list((selected_row or {}).get("hyphae_chain_addresses") or []),
            "hyphae_chain_length": int((selected_row or {}).get("hyphae_chain_length") or 0),
            "local_references": list((selected_row or {}).get("local_references") or []),
            "local_reference_count": int((selected_row or {}).get("local_reference_count") or 0),
            "raw": (selected_row or {}).get("raw"),
            "raw_json": _as_text((selected_row or {}).get("raw_json")),
        }

        query_summary_rows = [
            {"label": "document filter", "value": document_filter or "—"},
            {"label": "document sort", "value": document_sort_key},
            {"label": "document direction", "value": document_sort_direction},
            {"label": "row filter", "value": text_filter or "—"},
            {"label": "row sort", "value": row_sort_key},
            {"label": "row direction", "value": row_sort_direction},
            {"label": "group", "value": group_mode},
            {"label": "workbench lens", "value": workbench_lens},
            {"label": "source visibility", "value": source_visibility},
            {"label": "overlay visibility", "value": overlay_visibility},
        ]

        notes = [
            "Directive overlays are additive summaries only.",
            "Document filtering indexes version_hash and document identity fields.",
            "Row filtering indexes hyphae_hash, semantic identity, resolved lens, and row semantic fields.",
            "Hyphae identity comes from SQL semantic persistence; family and lens resolution remain presentation-only.",
            "Grouped datum views preserve canonical structural ordering within each section.",
            "No mutation controls are exposed on this surface.",
        ]

        inspector_sections = [
            {
                "title": "Selection",
                "rows": [
                    {"label": "document name", "value": selected_document_summary["document_name"] or "—"},
                    {"label": "document id", "value": selected_document_summary["document_id"] or "—"},
                    {"label": "document version hash", "value": selected_document_summary["version_hash"] or "—"},
                    {"label": "datum address", "value": selected_row_summary["datum_address"] or "—"},
                    {"label": "semantic hash", "value": selected_row_summary["semantic_hash"] or "—"},
                    {"label": "hyphae hash", "value": selected_row_summary["hyphae_hash"] or "—"},
                    {"label": "raw", "value": selected_row_summary["raw_json"] or "—"},
                ],
            }
        ]
        inspector_sections.append(
            {
                "title": "Lens Resolution",
                "rows": [
                    {"label": "display value", "value": selected_row_summary["display_value"] or "—"},
                    {"label": "display summary", "value": selected_row_summary["display_summary"] or "—"},
                    {"label": "recognized family", "value": selected_row_summary["recognized_family"] or "—"},
                    {"label": "recognized anchor", "value": selected_row_summary["recognized_anchor"] or "—"},
                    {"label": "primary value kind", "value": selected_row_summary["primary_value_kind"] or "—"},
                    {"label": "resolved lens", "value": selected_row_summary["resolved_lens"] or "—"},
                ],
            }
        )
        inspector_sections.append(
            {
                "title": "Hyphae Identity",
                "rows": [
                    {"label": "policy", "value": selected_row_summary["hyphae_policy"] or "—"},
                    {"label": "chain length", "value": str(selected_row_summary["hyphae_chain_length"])},
                    {"label": "local references", "value": _joined_tokens(selected_row_summary["local_references"]) or "—"},
                    {"label": "chain addresses", "value": _joined_tokens(selected_row_summary["hyphae_chain_addresses"]) or "—"},
                ],
            }
        )
        if source_visibility == "show":
            inspector_sections.append(
                {
                    "title": "Source Metadata",
                    "rows": [
                        {"label": "source kind", "value": selected_document_summary["source_kind"] or "—"},
                        {"label": "row count", "value": str(selected_document_summary["row_count"])},
                    ],
                }
            )
        inspector_sections.append(
            {
                "title": "Directive Overlay",
                "rows": _overlay_summary_rows(overlay, event_rows=overlay_events),
            }
        )

        document_section = {
            "title": "Document Table",
            "summary": "Read-only authoritative documents keyed by SQL version identity.",
            "sticky_header": True,
            "columns": _document_table_columns(source_visibility=source_visibility),
            "items": document_rows,
        }
        datum_section: dict[str, Any] = {
            "title": "Datum Grid",
            "summary": "Spreadsheet-like read-only rows keyed by row semantic identity.",
            "sticky_header": True,
            "columns": _datum_grid_columns(workbench_lens=workbench_lens),
            "items": visible_row_items,
        }
        if group_mode != "flat":
            datum_section["subsections"] = row_sections

        return {
            "tool_id": WORKBENCH_UI_TOOL_ID,
            "document_id": selected_document_id,
            "document_name": selected_document_summary["document_name"],
            "document_rows": document_rows,
            "document_filter": document_filter,
            "document_sort_key": document_sort_key,
            "document_sort_direction": document_sort_direction,
            "document_version_hash": document_version_hash,
            "document_version_hash_short": document_version_hash_short,
            "row_count": len(active_rows),
            "sort_key": row_sort_key,
            "sort_direction": row_sort_direction,
            "text_filter": text_filter,
            "group_mode": group_mode,
            "workbench_lens": workbench_lens,
            "source_visibility": source_visibility,
            "overlay_visibility": overlay_visibility,
            "rows": active_rows,
            "row_groups": row_groups,
            "selected_row": selected_row_summary,
            "selected_row_hyphae_hash_short": selected_row_summary["hyphae_hash_short"],
            "overlay": overlay,
            "overlay_events": overlay_events,
            "warnings": list(catalog.warnings),
            "navigation": navigation,
            "surface_payload": {
                "kind": "workbench_ui_surface",
                "tool_id": WORKBENCH_UI_TOOL_ID,
                "title": "Workbench UI",
                "subtitle": "Read-only two-pane SQL-backed spreadsheet with additive directive overlays.",
                "cards": [
                    {"label": "documents", "value": str(len(document_rows))},
                    {"label": "document", "value": selected_document_id or "—"},
                    {"label": "version", "value": document_version_hash_short or "—", "meta": document_version_hash or "—"},
                    {"label": "rows", "value": str(len(active_rows))},
                    {"label": "overlay", "value": overlay_visibility},
                ],
                "sections": [
                    document_section,
                    datum_section,
                    {
                        "title": "Query Controls",
                        "rows": query_summary_rows,
                    },
                ],
                "workspace": {
                    "query": {
                        "document": selected_document_id,
                        "document_filter": document_filter,
                        "document_sort": document_sort_key,
                        "document_dir": document_sort_direction,
                        "filter": text_filter,
                        "sort": row_sort_key,
                        "dir": row_sort_direction,
                        "group": group_mode,
                        "workbench_lens": workbench_lens,
                        "source": source_visibility,
                        "overlay": overlay_visibility,
                        "row": selected_row_summary["datum_address"],
                    },
                    "document_table": {
                        "sticky_header": True,
                        "columns": _document_table_columns(source_visibility=source_visibility),
                        "rows": document_rows,
                        "selected_document_id": selected_document_id,
                        "selected_marker": "selected",
                    },
                    "datum_grid": {
                        "sticky_header": True,
                        "columns": _datum_grid_columns(workbench_lens=workbench_lens),
                        "rows": visible_row_items,
                        "groups": row_groups,
                        "layers": layer_matrix,
                        "group_mode": group_mode,
                        "lens": workbench_lens,
                        "selected_row_id": selected_row_summary["datum_address"],
                        "selected_marker": "selected",
                    },
                    "selected_document": selected_document_summary,
                    "selected_row": selected_row_summary,
                    "navigation": navigation,
                    "source_visibility": source_visibility,
                    "overlay_visibility": overlay_visibility,
                },
                "notes": notes,
            },
            "inspector_sections": inspector_sections,
        }
