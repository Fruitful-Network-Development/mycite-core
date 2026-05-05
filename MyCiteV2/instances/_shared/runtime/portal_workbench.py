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
    if isinstance(document, dict):
        accessor = document.get
    else:
        accessor = lambda key, default=None: getattr(document, key, default)

    rows = accessor("rows") or accessor("datum_rows") or []
    if not isinstance(rows, list):
        rows = list(rows)
    return {
        "document_id": as_text(accessor("document_id")),
        "document_name": as_text(accessor("document_name") or accessor("name")),
        "relative_path": as_text(accessor("relative_path") or accessor("path")),
        "source_kind": as_text(accessor("source_kind") or accessor("kind")),
        "version_hash": as_text(accessor("version_hash")),
        "row_count": len(rows),
        "tool_id": as_text(accessor("tool_id") or accessor("sandbox") or accessor("sandbox_id")),
        "is_anchor": bool(accessor("is_anchor")),
        "legacy_alias": as_text(accessor("legacy_alias")),
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
            (card.get("document_name") or card.get("document_id") or "").lower(),
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

    del portal_scope, shell_state

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
            payload["layered_datum_table"] = {
                "document": _document_summary(focal_document),
                "rows": list(_as_list(getattr(focal_document, "rows", None) or _as_dict(focal_document).get("rows"))),
            }

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
