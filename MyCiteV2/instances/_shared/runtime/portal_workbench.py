"""Unified datum-file workbench builder.

This module exposes :func:`build_datum_file_workbench`, the single
shared builder used by every tool surface to project the centre
"workbench" region of the portal shell. The workbench is a state
machine reactive to the active sandbox:

* ``mode == "anchor"`` — the layered datum table of the sandbox's
  anchor file (``anthology`` for the SYSTEM sandbox, ``anchor`` for
  every tool sandbox).
* ``mode == "gallery"`` — a card grid of every document owned by the
  sandbox, used when the user has backed out of the anchor.
* ``mode == "selected_document"`` — the layered datum table of an
  explicitly selected document (gallery click).

The frontend dispatches on ``region.kind == "datum_file_workbench"``
and renders the appropriate sub-view based on ``mode``. Tool-specific
chrome (Diktataograph, Garland, manifest trees, analytics, …) does
not live in the workbench; it lives in the Interface Panel.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from MyCiteV2.instances._shared.runtime.runtime_platform import (
    PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
    attach_region_family_contract,
)
from MyCiteV2.packages.modules.shared.scalars import as_text
from MyCiteV2.packages.state_machine.portal_shell import PortalScope, PortalShellState

PORTAL_SHELL_REGION_DATUM_FILE_WORKBENCH_SCHEMA = "mycite.v2.portal.shell.region.workbench.v2"
DATUM_FILE_WORKBENCH_KIND = "datum_file_workbench"

WORKBENCH_MODE_ANCHOR = "anchor"
WORKBENCH_MODE_GALLERY = "gallery"
WORKBENCH_MODE_SELECTED_DOCUMENT = "selected_document"
WORKBENCH_MODES = (
    WORKBENCH_MODE_ANCHOR,
    WORKBENCH_MODE_GALLERY,
    WORKBENCH_MODE_SELECTED_DOCUMENT,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {as_text(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return as_text(value)


def _accessor_for(value: Any):
    if isinstance(value, dict):
        return value.get
    return lambda key, default=None: getattr(value, key, default)


def _document_object(document: Any | None) -> Any | None:
    if isinstance(document, dict) and document.get("document") is not None:
        return document.get("document")
    return document


def _document_rows(document: Any | None) -> list[Any]:
    if document is None:
        return []
    sources: list[Any] = []
    if isinstance(document, dict):
        sources.extend(
            [
                document.get("rows"),
                document.get("datum_rows"),
                (_as_dict(document.get("document")).get("rows") if isinstance(document.get("document"), dict) else None),
            ]
        )
        nested = document.get("document")
        if nested is not None and not isinstance(nested, dict):
            sources.append(getattr(nested, "rows", None))
            sources.append(getattr(nested, "datum_rows", None))
    else:
        sources.extend([getattr(document, "rows", None), getattr(document, "datum_rows", None)])
    for rows in sources:
        if rows is None:
            continue
        if isinstance(rows, list):
            return rows
        try:
            return list(rows)
        except TypeError:
            continue
    return []


def _document_summary(document: Any | None) -> dict[str, Any]:
    """Return a normalized summary projection of a datum document.

    Accepts either a dict or an object with the canonical
    ``document_id``, ``document_name``, ``relative_path``,
    ``source_kind``, ``version_hash``, ``rows`` and ``tool_id``
    attributes/keys. Unknown values fall back to empty strings or
    zero-length collections so callers can rely on a stable shape.
    """

    if document is None:
        return {}
    if hasattr(document, "to_summary_dict"):
        summary = getattr(document, "to_summary_dict")()
        if isinstance(summary, dict):
            document = summary
    if isinstance(document, dict) and isinstance(document.get("document_summary"), dict):
        summary = dict(document.get("document_summary") or {})
        nested = _document_object(document)
        nested_rows = _document_rows(nested)
        metadata = summary.get("document_metadata") if isinstance(summary.get("document_metadata"), dict) else {}
        if nested_rows and not summary.get("row_count"):
            summary["row_count"] = len(nested_rows)
        if not summary.get("is_anchor") and isinstance(nested, object):
            summary["is_anchor"] = bool(getattr(nested, "is_anchor", False))
        if not summary.get("canonical_name") and isinstance(nested, object):
            summary["canonical_name"] = as_text(getattr(nested, "canonical_name", ""))
        return {
            "document_id": as_text(summary.get("document_id")),
            "document_name": as_text(summary.get("document_name") or summary.get("name")),
            "canonical_name": as_text(summary.get("canonical_name")),
            "relative_path": as_text(summary.get("relative_path") or summary.get("path")),
            "source_kind": as_text(summary.get("source_kind") or summary.get("kind")),
            "version_hash": as_text(summary.get("version_hash")),
            "row_count": int(summary.get("row_count") or 0),
            "tool_id": as_text(summary.get("tool_id") or summary.get("sandbox") or summary.get("sandbox_id")),
            "is_anchor": bool(summary.get("is_anchor")),
            "legacy_alias": as_text(summary.get("legacy_alias") or metadata.get("legacy_alias")),
        }
    accessor = _accessor_for(document)

    rows = _document_rows(document)
    metadata = _as_dict(accessor("document_metadata"))
    return {
        "document_id": as_text(accessor("document_id")),
        "document_name": as_text(accessor("document_name") or accessor("name")),
        "canonical_name": as_text(accessor("canonical_name")),
        "relative_path": as_text(accessor("relative_path") or accessor("path")),
        "source_kind": as_text(accessor("source_kind") or accessor("kind")),
        "version_hash": as_text(accessor("version_hash")),
        "row_count": len(rows),
        "tool_id": as_text(accessor("tool_id") or accessor("sandbox") or accessor("sandbox_id")),
        "is_anchor": bool(accessor("is_anchor")),
        "legacy_alias": as_text(accessor("legacy_alias") or metadata.get("legacy_alias")),
    }


def _datum_coordinates(datum_id: object) -> dict[str, int] | None:
    token = as_text(datum_id)
    parts = token.split("-")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return {
        "layer": int(parts[0]),
        "value_group": int(parts[1]),
        "iteration": int(parts[2]),
    }


def _row_value(row: Any, key: str, default: Any = "") -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _row_label(row: Any, datum_id: str) -> str:
    labels = _row_value(row, "labels", ())
    if labels:
        try:
            first = list(labels)[0]
            if as_text(first):
                return as_text(first)
        except TypeError:
            pass
    return as_text(_row_value(row, "label")) or datum_id or "Datum"


def _row_item(
    row: Any,
    *,
    document_id: str,
    sandbox_id: str,
    selected_datum_id: str,
) -> dict[str, Any]:
    datum_id = as_text(_row_value(row, "datum_id") or _row_value(row, "datum_address"))
    primary_value = as_text(
        _row_value(row, "display_value")
        or _row_value(row, "primary_value_token")
        or _row_value(row, "value_token")
        or _row_value(row, "value")
    )
    diagnostics = _row_value(row, "diagnostic_states", ()) or ()
    try:
        diagnostics_list = [as_text(item) for item in list(diagnostics) if as_text(item)]
    except TypeError:
        diagnostics_list = [as_text(diagnostics)] if as_text(diagnostics) else []
    item = {
        "datum_id": datum_id,
        "datum_address": datum_id,
        "label": _row_label(row, datum_id),
        "coordinates": _datum_coordinates(datum_id),
        "selected": datum_id == selected_datum_id,
        "display_value": primary_value,
        "primary_value_token": primary_value,
        "recognized_family": as_text(_row_value(row, "recognized_family")),
        "recognized_anchor": as_text(_row_value(row, "recognized_anchor")),
        "diagnostics": diagnostics_list,
        "raw": _json_safe(_row_value(row, "raw", row if isinstance(row, dict) else None)),
        "edit_actions": [
            {
                "action": "update_row_raw",
                "label": "Edit",
                "target_authority": "datum_workbench",
                "sandbox_id": sandbox_id,
                "document_id": document_id,
                "datum_address": datum_id,
                "endpoint": "/portal/api/v2/mutations/stage",
            }
        ],
    }
    return item


def _sort_group_token(token: object) -> tuple[int, object]:
    return (0, token) if isinstance(token, int) else (1, as_text(token))


def _layer_groups_for_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[object, object], list[dict[str, Any]]] = {}
    layer_meta: dict[object, dict[str, Any]] = {}
    value_group_meta: dict[tuple[object, object], dict[str, Any]] = {}
    for item in rows:
        datum_id = as_text(item.get("datum_id"))
        if not datum_id:
            continue
        coordinates = _as_dict(item.get("coordinates"))
        layer = coordinates.get("layer")
        value_group = coordinates.get("value_group")
        layer_key: object = layer if isinstance(layer, int) else "unstructured"
        value_group_key: object = value_group if isinstance(value_group, int) else "unstructured"
        grouped.setdefault((layer_key, value_group_key), []).append(item)
        layer_meta.setdefault(
            layer_key,
            {
                "layer": layer if isinstance(layer, int) else None,
                "label": f"Layer {layer}" if isinstance(layer, int) else "Unstructured",
            },
        )
        value_group_meta.setdefault(
            (layer_key, value_group_key),
            {
                "value_group": value_group if isinstance(value_group, int) else None,
                "label": f"Value Group {value_group}" if isinstance(value_group, int) else "Unstructured",
            },
        )
    layer_groups: list[dict[str, Any]] = []
    for layer_key in sorted({pair[0] for pair in grouped}, key=_sort_group_token):
        value_groups: list[dict[str, Any]] = []
        layer_row_count = 0
        layer_selected = False
        pairs = sorted([pair for pair in grouped if pair[0] == layer_key], key=lambda pair: _sort_group_token(pair[1]))
        for pair in pairs:
            vg_rows = sorted(
                grouped[pair],
                key=lambda item: (
                    (_as_dict(item.get("coordinates")).get("iteration") if isinstance(_as_dict(item.get("coordinates")).get("iteration"), int) else 10**9),
                    as_text(item.get("datum_id")),
                ),
            )
            selected = any(bool(item.get("selected")) for item in vg_rows)
            layer_selected = layer_selected or selected
            layer_row_count += len(vg_rows)
            value_groups.append(
                {
                    "value_group": value_group_meta[pair]["value_group"],
                    "label": value_group_meta[pair]["label"],
                    "row_count": len(vg_rows),
                    "selected": selected,
                    "rows": vg_rows,
                }
            )
        layer_groups.append(
            {
                "layer": layer_meta[layer_key]["layer"],
                "label": layer_meta[layer_key]["label"],
                "row_count": layer_row_count,
                "selected": layer_selected,
                "value_groups": value_groups,
            }
        )
    return layer_groups


def _selected_datum_id(shell_state: PortalShellState | None) -> str:
    if shell_state is None:
        return ""
    state = shell_state if isinstance(shell_state, PortalShellState) else PortalShellState.from_value(shell_state)
    for segment in state.focus_path:
        if segment.level == "datum":
            return segment.id
    return ""


def _layered_table_for_document(
    document: Any,
    *,
    sandbox_id: str,
    selected_datum_id: str,
) -> dict[str, Any]:
    summary = _document_summary(document)
    document_id = as_text(summary.get("document_id"))
    row_items = [
        _row_item(row, document_id=document_id, sandbox_id=sandbox_id, selected_datum_id=selected_datum_id)
        for row in _document_rows(document)
    ]
    return {
        "document": summary,
        "rows": row_items,
        "layer_groups": _layer_groups_for_rows(row_items),
        "mutation_contract": {
            "target_authority": "datum_workbench",
            "sandbox_id": sandbox_id,
            "document_id": document_id,
            "stages": ["stage", "validate", "preview", "apply", "discard"],
            "operations": ["update_row_raw", "insert_datum", "delete_datum", "move_datum"],
        },
    }


def _gallery_card_for_document(
    document: Any,
    *,
    sandbox_id: str,
    selected_document_id: str = "",
) -> dict[str, Any]:
    summary = _document_summary(document)
    if not summary:
        return {}
    summary["sandbox_id"] = sandbox_id
    summary["label"] = summary.get("canonical_name") or summary.get("document_name") or summary.get("document_id") or ""
    summary["secondary_label"] = summary.get("document_name") or summary.get("relative_path") or ""
    summary["shell_transition"] = {
        "kind": "focus_file",
        "file_key": summary.get("document_id") or "",
    }
    summary["selected"] = bool(
        selected_document_id and summary.get("document_id") == selected_document_id
    )
    return summary


def _gallery_cards(
    documents: list[Any],
    *,
    sandbox_id: str,
    selected_document_id: str,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for document in documents:
        card = _gallery_card_for_document(
            document,
            sandbox_id=sandbox_id,
            selected_document_id=selected_document_id,
        )
        if card:
            cards.append(card)
    cards.sort(
        key=lambda card: (
            0 if card.get("is_anchor") else 1,
            (card.get("canonical_name") or card.get("document_name") or card.get("document_id") or "").lower(),
        )
    )
    return cards


def _resolve_mode(
    *,
    anchor_document: Any | None,
    selected_document: Any | None,
    explicit_mode: str | None,
) -> str:
    """Resolve the workbench mode from inputs.

    Explicit mode (when valid) wins. Otherwise: anchor mode when
    a sandbox anchor is provided and no other selection exists;
    selected_document when a non-anchor selection is provided;
    gallery when no selection at all.
    """

    if explicit_mode in WORKBENCH_MODES:
        return explicit_mode
    selected_summary = _document_summary(selected_document)
    anchor_summary = _document_summary(anchor_document)
    selected_id = selected_summary.get("document_id")
    anchor_id = anchor_summary.get("document_id")
    if selected_id and selected_id != anchor_id:
        return WORKBENCH_MODE_SELECTED_DOCUMENT
    if anchor_id:
        return WORKBENCH_MODE_ANCHOR
    return WORKBENCH_MODE_GALLERY


def build_datum_file_workbench(
    *,
    portal_scope: PortalScope,
    shell_state: PortalShellState | None,
    surface_id: str,
    sandbox_id: str,
    sandbox_label: str = "",
    anchor_document: Any | None = None,
    selected_document: Any | None = None,
    sandbox_documents: list[Any] | None = None,
    explicit_mode: str | None = None,
    title: str = "Datum File Workbench",
    subtitle: str = "",
    visible: bool = True,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct the canonical ``datum_file_workbench`` region payload.

    Returns a region dict with kind ``datum_file_workbench`` carrying
    the resolved ``mode`` plus mode-specific projections. The frontend
    dispatch picks ``renderLayeredDatumTable`` for ``anchor`` and
    ``selected_document`` modes, and ``renderSandboxDocumentGallery``
    for ``gallery`` mode.

    Tool surfaces pass:
      * ``sandbox_id`` — canonical sandbox segment (``"system"``,
        ``"cts-gis"``, ``"aws-csm"``, …)
      * ``anchor_document`` — the sandbox's anchor file projection
      * ``selected_document`` — the focused datum file (may be the
        anchor itself or a sibling)
      * ``sandbox_documents`` — every datum document owned by
        ``sandbox_id``, used to render the gallery

    Workbench-UI is the documented exception: it keeps its bespoke
    SQL row-grid as a workbench-primary surface and does not call
    this builder.
    """

    mode = _resolve_mode(
        anchor_document=anchor_document,
        selected_document=selected_document,
        explicit_mode=explicit_mode,
    )

    anchor_summary = _document_summary(anchor_document)
    selected_summary = _document_summary(selected_document)
    documents = _as_list(sandbox_documents)

    payload: dict[str, Any] = {
        "schema": PORTAL_SHELL_REGION_DATUM_FILE_WORKBENCH_SCHEMA,
        "kind": DATUM_FILE_WORKBENCH_KIND,
        "title": title,
        "subtitle": subtitle,
        "visible": visible,
        "mode": mode,
        "sandbox": {
            "id": sandbox_id,
            "label": sandbox_label or sandbox_id,
        },
        "anchor": anchor_summary or None,
        "selected_document": selected_summary or None,
        "portal_scope": portal_scope.to_dict() if isinstance(portal_scope, PortalScope) else {},
    }

    if mode == WORKBENCH_MODE_GALLERY:
        payload["gallery"] = {
            "sandbox_id": sandbox_id,
            "documents": _gallery_cards(
                documents,
                sandbox_id=sandbox_id,
                selected_document_id=selected_summary.get("document_id") or "",
            ),
        }
    elif mode in (WORKBENCH_MODE_ANCHOR, WORKBENCH_MODE_SELECTED_DOCUMENT):
        focal_document = anchor_document if mode == WORKBENCH_MODE_ANCHOR else selected_document
        if focal_document is not None:
            payload["layered_datum_table"] = _layered_table_for_document(
                focal_document,
                sandbox_id=sandbox_id,
                selected_datum_id=_selected_datum_id(shell_state),
            )

    if isinstance(extra_payload, dict):
        for key, value in extra_payload.items():
            payload.setdefault(key, value)

    return attach_region_family_contract(
        payload,
        family=PORTAL_REGION_FAMILY_REFLECTIVE_WORKSPACE,
        surface_id=surface_id,
    )


__all__ = [
    "build_datum_file_workbench",
    "PORTAL_SHELL_REGION_DATUM_FILE_WORKBENCH_SCHEMA",
    "DATUM_FILE_WORKBENCH_KIND",
    "WORKBENCH_MODE_ANCHOR",
    "WORKBENCH_MODE_GALLERY",
    "WORKBENCH_MODE_SELECTED_DOCUMENT",
    "WORKBENCH_MODES",
]
