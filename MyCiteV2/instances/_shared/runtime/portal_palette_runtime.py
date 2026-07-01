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
    all_tools as _viz_all_tools,
)
from MyCiteV2.packages.tools._archetype import document_archetypes as _document_archetypes
from MyCiteV2.packages.tools._shared.utilities import as_text as _as_text

PORTAL_PALETTE_RESPONSE_SCHEMA = "mycite.v2.portal.palette.eligible_tools.response.v1"

# Operator decision (portal-tool-overlay-restructure): the portal collapses to a single live
# tool — the agronomics workbench — plus the two viewers it consolidates. Every other
# registered viz tool is legacy. The HTTP palette endpoints pass ``live_only=True`` so the
# menubar search dropdown lists exactly {agronomics, farm_profile, samras_structure} (an
# explicit allow-list — eligibility alone would still surface contacts/invoices/plots/
# contracts/product for the agro_erp sandbox). The response builders default to UNFILTERED
# (full eligibility) so the eligibility logic stays independently testable; only the search
# opts in. Legacy tools stay registered + renderable via a direct surface_query.tools — they
# are just no longer discoverable in the search.
LIVE_TOOL_IDS: tuple[str, ...] = (
    "agronomics", "farm_profile", "samras_structure", "local_domain",
    "invoices", "contracts", "inventory_synopsis", "plot_manager", "contract_editor",
)


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


def derive_document_archetypes(datum_doc: Any) -> set[str]:
    """Recognize a document's tool-eligibility archetypes (TASK-2026-06-02-008).

    Delegates to the single-sourced recognizer in
    :mod:`MyCiteV2.packages.tools._archetype` so the palette eligibility, the
    farm-profile viewer, and the contracts tool all agree on what a document IS
    (notably the tightened ``hops_geospatial_filament`` rule: a family-4 ring row
    carrying rf.3-1-3, not merely any stray rf.3-1-3 token).
    """
    return _document_archetypes(datum_doc)


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
    live_only: bool = False,
) -> dict[str, Any]:
    """Return ``{schema, tools: [...]}`` for the menubar palette.

    Plan v2: tools come from the viz-tool registry. When the user has
    selected a document we filter by applies_to_archetype /
    applies_to_source_kind against the document's metadata. When no
    document is selected we return every registered tool so the
    menubar search input is useful immediately after page load.

    ``live_only`` (set by the HTTP endpoint) further restricts the result to
    :data:`LIVE_TOOL_IDS` so the search dropdown lists only the live tools;
    the default (False) returns full eligibility for testing/inspection.
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
            archetypes |= derive_document_archetypes(datum_doc)
            source_kind = _as_text(getattr(datum_doc, "source_kind", ""))
            if source_kind:
                source_kinds.add(source_kind)

    matching = [
        tool for tool in _viz_all_tools()
        if (not live_only or tool.tool_id in LIVE_TOOL_IDS)
        and _viz_tool_matches(tool, archetypes=archetypes, source_kinds=source_kinds)
    ]
    return {
        "schema": PORTAL_PALETTE_RESPONSE_SCHEMA,
        "tools": [
            {
                "tool_id": tool.tool_id,
                "label": tool.label,
                "summary": tool.summary,
                # ``route`` is what the JS palette stamps on each item's
                # data-route attribute and dispatches on click
                # (v2_portal_tool_palette.js renderList). When the iterable
                # element doesn't carry a route attribute (the lightweight
                # WorkbenchTool protocol omits it; PortalToolRegistryEntry
                # provides it), fall back to "" so the schema stays stable.
                "route": _as_text(getattr(tool, "route", "")),
            }
            for tool in matching
        ],
    }


PORTAL_SANDBOX_VISUALIZERS_SCHEMA = "mycite.v2.portal.visualizers.for_sandbox.response.v1"


def _doc_sandbox(doc: Any) -> str:
    # Canonical id is lv.<msn>.<sandbox>.<name>.<hash> → sandbox is parts[2].
    parts = _as_text(getattr(doc, "document_id", "")).split(".")
    return parts[2] if len(parts) > 4 else ""


def _doc_name(doc: Any) -> str:
    parts = _as_text(getattr(doc, "document_id", "")).split(".")
    return parts[3] if len(parts) > 4 else ""


def _doc_eligibility(doc: Any) -> tuple[set[str], set[str], str]:
    # Single-sourced recognition (audit Theme G fix): delegate to the same
    # derive_document_archetypes() the document-context path uses, so the
    # sandbox-visualizers path also sees structural archetypes (e.g. the
    # HOPS hops_geospatial_filament scan), not just metadata tokens. Prevents a
    # tool being eligible on one path but not the other.
    archetypes = derive_document_archetypes(doc)
    source_kind = _as_text(getattr(doc, "source_kind", ""))
    return archetypes, ({source_kind} if source_kind else set()), source_kind


def build_sandbox_visualizers_response(
    *, tenant_id: str, sandbox_id: str, datum_store: Any, live_only: bool = False
) -> dict[str, Any]:
    """Return the visualizers eligible for the contents of one sandbox.

    Powers the menubar search bar: rather than answering "which tools fit THIS
    selected document", it scans every document in ``sandbox_id`` and returns the
    union of eligible visualizers (ranked by how many of the sandbox's documents
    each one can render), plus the document list and the set of known sandboxes.
    When ``sandbox_id`` is empty every document is considered (corpus-wide).
    """
    tenant_id = _as_text(tenant_id)
    sandbox_id = _as_text(sandbox_id)

    docs: list[Any] = []
    if datum_store is not None:
        try:
            catalog = datum_store.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id=tenant_id)
            )
            docs = list(getattr(catalog, "documents", ()) or ())
        except Exception:
            docs = []

    sandboxes = sorted({s for s in (_doc_sandbox(d) for d in docs) if s})
    in_sandbox = [d for d in docs if (not sandbox_id or _doc_sandbox(d) == sandbox_id)]

    documents_out: list[dict[str, Any]] = []
    hits: dict[str, dict[str, Any]] = {}
    for doc in in_sandbox:
        archetypes, source_kinds, source_kind = _doc_eligibility(doc)
        doc_id = _as_text(getattr(doc, "document_id", ""))
        documents_out.append({
            "document_id": doc_id,
            "name": _doc_name(doc),
            "archetype": next(iter(archetypes), ""),
            "source_kind": source_kind,
            "row_count": len(getattr(doc, "rows", ()) or ()),
        })
        for tool in _viz_all_tools():
            if live_only and tool.tool_id not in LIVE_TOOL_IDS:
                continue
            if _viz_tool_matches(tool, archetypes=archetypes, source_kinds=source_kinds):
                entry = hits.setdefault(tool.tool_id, {"tool": tool, "documents": []})
                entry["documents"].append(doc_id)

    visualizers = []
    for tool_id in sorted(hits):
        tool = hits[tool_id]["tool"]
        eligible_docs = hits[tool_id]["documents"]
        visualizers.append({
            "tool_id": tool.tool_id,
            "label": tool.label,
            "summary": tool.summary,
            "route": _as_text(getattr(tool, "route", "")),
            "eligible_count": len(eligible_docs),
            "eligible_documents": eligible_docs,
        })
    # Rank by reach (documents covered) then id, so the most broadly-useful
    # visualizer for the sandbox sorts to the top of the search list.
    visualizers.sort(key=lambda v: (-v["eligible_count"], v["tool_id"]))

    return {
        "schema": PORTAL_SANDBOX_VISUALIZERS_SCHEMA,
        "sandbox_id": sandbox_id,
        "sandboxes": sandboxes,
        "documents": documents_out,
        "visualizers": visualizers,
    }


__all__ = [
    "LIVE_TOOL_IDS",
    "PORTAL_PALETTE_RESPONSE_SCHEMA",
    "PORTAL_SANDBOX_VISUALIZERS_SCHEMA",
    "build_eligible_tools_response",
    "build_sandbox_visualizers_response",
]
