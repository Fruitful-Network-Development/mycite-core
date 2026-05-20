"""Palette runtime.

Resolves the eligible palette tools for a selected datum and returns a
response payload suitable for GET /portal/api/tools/eligible. The HTTP
endpoint is wired in instances/_shared/portal_host/app.py.

Plan v2: the palette now reads from
:mod:`MyCiteV2.packages.tools` (the new viz-tool registry). Tools no
longer own surfaces or routes — they render into the workbench's
visualization panel when invoked. When no datum is selected the palette
returns every registered viz tool so the menubar search input still
shows useful options on first load.

Original Phase 3 doc (portal_tool_surface_contract.md): the palette
replaces the interface panel as the surface that lists which tools can
be applied to the currently-selected datum.
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.packages.tools import (
    TOOL_REGISTRY as _VIZ_TOOL_REGISTRY,
    all_tools as _viz_all_tools,
)

PORTAL_PALETTE_RESPONSE_SCHEMA = "mycite.v2.portal.palette.eligible_tools.response.v1"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _find_document(
    *, tenant_id: str, document_id: str, datum_store: Any
) -> AuthoritativeDatumDocument | None:
    """Look up a document by id. Returns None when the store is unavailable or
    the id is not in the catalog."""
    if datum_store is None or not document_id:
        return None
    try:
        catalog = datum_store.read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
        )
    except Exception:
        return None
    for doc in getattr(catalog, "documents", ()) or ():
        if getattr(doc, "document_id", "") == document_id:
            return doc
    return None


def _viz_tool_matches(
    tool: Any, *, archetypes: set[str], source_kinds: set[str]
) -> bool:
    """Eligibility predicate for a viz tool against a datum's metadata.

    A tool matches when at least one of its applies_to_archetype or
    applies_to_source_kind intersects with the document's tokens.
    Empty applies_to lists are treated as "universal" — the tool
    matches every datum. When the caller has no document context
    (archetypes and source_kinds are both empty), every tool is
    returned so the menubar search is useful on first load.
    """
    if not archetypes and not source_kinds:
        return True
    tool_archetypes = set(getattr(tool, "applies_to_archetype", ()) or ())
    tool_source_kinds = set(getattr(tool, "applies_to_source_kind", ()) or ())
    if not tool_archetypes and not tool_source_kinds:
        return True
    return bool(tool_archetypes & archetypes) or bool(tool_source_kinds & source_kinds)


def build_eligible_tools_response(
    *,
    tenant_id: str,
    document_id: str,
    datum_address: str,
    datum_store: Any,
) -> dict[str, Any]:
    """Return ``{schema, tools: [...]}`` for the menubar palette.

    Plan v2: tools come from the viz-tool registry. When the user has
    selected a document we filter by applies_to_archetype /
    applies_to_source_kind against the document's metadata. When no
    document is selected we return every registered tool so the
    menubar search input is useful immediately after page load.
    """
    tenant_id = _as_text(tenant_id)
    document_id = _as_text(document_id)
    datum_address = _as_text(datum_address)

    archetypes: set[str] = set()
    source_kinds: set[str] = set()
    if tenant_id and document_id:
        datum_doc = _find_document(
            tenant_id=tenant_id, document_id=document_id, datum_store=datum_store
        )
        if datum_doc is not None:
            metadata = getattr(datum_doc, "document_metadata", None) or {}
            archetype = _as_text(metadata.get("datum_template_archetype") if isinstance(metadata, dict) else "")
            if archetype:
                archetypes.add(archetype)
            family = _as_text(metadata.get("samras_family") if isinstance(metadata, dict) else "")
            if family:
                archetypes.add(family)
            source_kind = _as_text(getattr(datum_doc, "source_kind", ""))
            if source_kind:
                source_kinds.add(source_kind)

    matching = [
        tool for tool in _viz_all_tools()
        if _viz_tool_matches(tool, archetypes=archetypes, source_kinds=source_kinds)
    ]
    return {
        "schema": PORTAL_PALETTE_RESPONSE_SCHEMA,
        "tools": [
            {
                "tool_id": tool.tool_id,
                "label": tool.label,
                "summary": tool.summary,
                "route": "",
            }
            for tool in matching
        ],
    }


__all__ = [
    "PORTAL_PALETTE_RESPONSE_SCHEMA",
    "build_eligible_tools_response",
]
