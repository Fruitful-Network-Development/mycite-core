"""Phase 3 — palette runtime.

Resolves the eligible palette tools for a selected datum and returns a
response payload suitable for GET /portal/api/tools/eligible. The HTTP
endpoint is wired in instances/_shared/portal_host/app.py.

See portal_tool_surface_contract.md for the architectural intent: the
palette replaces the interface panel as the surface that lists which tools
can be applied to the currently-selected datum.
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.packages.state_machine.portal_shell import (
    build_portal_tool_registry_entries,
)
from MyCiteV2.packages.state_machine.portal_shell.tool_eligibility import (
    recognize_applicable_tools,
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


def build_eligible_tools_response(
    *,
    tenant_id: str,
    document_id: str,
    datum_address: str,
    datum_store: Any,
) -> dict[str, Any]:
    """Return ``{schema, tools: [...]}`` for a given selected datum.

    Empty inputs produce an empty list rather than an error. Tool entries
    surface only the fields the palette UI needs (tool_id, label, summary,
    route). Sort order is deterministic via tool_id (enforced inside
    recognize_applicable_tools).
    """
    tenant_id = _as_text(tenant_id)
    document_id = _as_text(document_id)
    datum_address = _as_text(datum_address)
    if not (tenant_id and document_id and datum_address):
        return {"schema": PORTAL_PALETTE_RESPONSE_SCHEMA, "tools": []}

    datum_doc = _find_document(
        tenant_id=tenant_id, document_id=document_id, datum_store=datum_store
    )
    if datum_doc is None:
        return {"schema": PORTAL_PALETTE_RESPONSE_SCHEMA, "tools": []}

    eligible = recognize_applicable_tools(
        datum_doc, datum_address, build_portal_tool_registry_entries()
    )
    return {
        "schema": PORTAL_PALETTE_RESPONSE_SCHEMA,
        "tools": [
            {
                "tool_id": entry.tool_id,
                "label": entry.label,
                "summary": entry.summary,
                "route": entry.route,
            }
            for entry in eligible
        ],
    }


__all__ = [
    "PORTAL_PALETTE_RESPONSE_SCHEMA",
    "build_eligible_tools_response",
]
