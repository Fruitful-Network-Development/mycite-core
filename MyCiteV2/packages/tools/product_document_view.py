"""Product-document viewer — the first content-resolving Plan-v2 visualizer.

Renders an agro_erp ``product_profiles`` document (value-group-9 PAIRS rows) as a
human-readable product table: each row's ``product_id`` (an LCL product-leaf node
address) is resolved to the product NAME via a cross-document index over the
``lcl`` document, the ``taxonomy_id`` is resolved to its taxon title via ``txa``,
and the four classification references + the two unit magnitudes (gestation in
seconds, spacing in centimetres) are surfaced with their field labels.

This is the concrete proof of the "tools = a library of UI objects that view the
visualized target datum" convention: it composes a panel payload purely from the
sandbox's own documents, including the **cross-document** product_id→name lookup
that the document-local recognition layer does not perform. The resolver
(:class:`LclNameIndex`) is memoized per (document_id) so the 1.6k-entry binary
decode is not repeated per render.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import NameIndex, cached_index, decode_label
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
)
from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._archetype import read_sandbox_catalog
from ._registry import register
from ._shared.utilities import as_text as _as_text

# Back-compat alias: the cross-tool resolver now lives in datum_ops.datum_resolve
# (shape-based scan + shared cache). txa_tree / contracts import this name from here.
LclNameIndex = NameIndex

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.product_document.v1"

# Field labels for the 9 value-group pairs, in head order. Mirrors the
# product_profile.yaml value_group_reference_design (kept in sync there).
_PAIR_FIELDS: tuple[str, ...] = (
    "product_id",
    "taxonomy_id",
    "rotation_group",
    "propagule",
    "genesis",
    "ownership",
    "raunkiaerality",
    "gestation",
    "spacing",
    "singular_unit_weight",
)
# Which fields resolve against which sibling document's node→label index.
_LCL_FIELDS = {"product_id", "rotation_group", "propagule", "genesis", "ownership", "raunkiaerality"}
_TXA_FIELDS = {"taxonomy_id"}
_UNIT_FIELDS = {"gestation", "spacing"}
# Nominal (136-bit ASCII) fields → decode to text (e.g. "0.07 g").
_NOMINAL_FIELDS = {"singular_unit_weight"}


def _rows(document: AuthoritativeDatumDocument) -> list[Any]:
    out = []
    for r in getattr(document, "rows", ()) or ():
        if hasattr(r, "datum_address"):
            out.append(r)
        elif isinstance(r, dict):
            out.append(type("Row", (), {"datum_address": r.get("datum_address", ""), "raw": r.get("raw")})())
    return out


class ProductDocumentViewer:
    """Resolve an agro_erp ``product_profiles`` doc into a labelled product table."""

    tool_id = "product_document"
    label = "Product Document Viewer"
    summary = "Products with names, taxonomy, classification and unit magnitudes resolved from the sandbox."
    route = WORKBENCH_UI_TOOL_ROUTE
    applies_to_archetype: tuple[str, ...] = ("agro_erp_product_profile_row",)
    # Intentionally NOT source-kind-matched: the product viewer is specific to the
    # product_profile archetype, not to every sandbox_source document. (The match
    # predicate ORs archetype/source_kind, so declaring sandbox_source here would
    # make the viewer eligible for anchor/txa/lcl too.)
    applies_to_source_kind: tuple[str, ...] = ()

    def build_panel_payload(
        self,
        *,
        authority_db_file: Path | None,
        sandbox_id: str,
        document_id: str,
        datum_address: str,
    ) -> dict[str, Any]:
        docs, err = read_sandbox_catalog(authority_db_file, tenant_id=_TENANT_DEFAULT)
        if err:
            return _error(err)
        product_doc = next((d for d in docs if _as_text(getattr(d, "document_id", "")) == _as_text(document_id)), None)
        if product_doc is None:
            # fall back to the named product_profiles doc in the sandbox
            product_doc = _find_named(docs, sandbox_id or "agro_erp", "product_profiles")
        if product_doc is None:
            return _error("product_profiles document not found")

        sandbox = sandbox_id or _sandbox_of(product_doc) or "agro_erp"
        lcl_index = cached_index(_find_named(docs, sandbox, "lcl"))
        txa_index = cached_index(_find_named(docs, sandbox, "txa"))

        products = build_product_rows(product_doc, lcl_index=lcl_index, txa_index=txa_index)

        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox,
            "document_id": _as_text(getattr(product_doc, "document_id", "")),
            "selected_row_address": _as_text(datum_address),
            "columns": list(_PAIR_FIELDS),
            "product_count": len(products),
            "lcl_index_size": len(lcl_index),
            "products": products,
        }


def build_product_rows(
    product_doc: AuthoritativeDatumDocument,
    *,
    lcl_index: LclNameIndex,
    txa_index: LclNameIndex,
) -> list[dict[str, Any]]:
    """Resolve every ``4-9-*`` vg-9 row into a labelled product dict (pure)."""
    products: list[dict[str, Any]] = []
    for row in _rows(product_doc):
        addr = _as_text(row.datum_address)
        if not addr.startswith("4-10-"):  # vg-10 since the singular_unit_weight append
            continue
        raw = row.raw
        if not (isinstance(raw, list) and raw and isinstance(raw[0], list)):
            continue
        head = raw[0]
        product_name = ""
        if len(raw) > 1 and isinstance(raw[1], list) and raw[1]:
            product_name = _as_text(raw[1][0])
        fields: list[dict[str, Any]] = []
        # head = [addr, (ref, mag) x 9]; pair i -> _PAIR_FIELDS[i]
        for i, field in enumerate(_PAIR_FIELDS):
            mag_index = 2 + 2 * i
            if mag_index >= len(head):
                break
            magnitude = _as_text(head[mag_index])
            resolved = ""
            if field in _LCL_FIELDS:
                resolved = lcl_index.resolve(magnitude)
            elif field in _TXA_FIELDS:
                resolved = txa_index.resolve(magnitude)
            elif field in _NOMINAL_FIELDS:
                resolved = decode_label(magnitude)  # 136-bit ASCII nominal → "0.07 g"
            elif field in _UNIT_FIELDS:
                resolved = magnitude  # already a scalar count
            if field == "product_id" and resolved:
                product_name = resolved
            fields.append({"field": field, "magnitude": magnitude, "resolved": resolved})
        products.append({
            "datum_address": addr,
            "product_name": product_name,
            "fields": fields,
        })
    return products


def _find_named(docs: list[Any], sandbox_id: str, name: str) -> AuthoritativeDatumDocument | None:
    marker = f".{sandbox_id}."
    for d in docs:
        did = _as_text(getattr(d, "document_id", ""))
        parts = did.split(".")
        if marker in did and len(parts) > 3 and parts[3] == name:
            return d
    return None


def _sandbox_of(document: AuthoritativeDatumDocument) -> str:
    # Canonical id is lv.<msn>.<sandbox>.<name>.<hash> → sandbox is parts[2].
    parts = _as_text(getattr(document, "document_id", "")).split(".")
    return parts[2] if len(parts) > 4 else ""


def _error(message: str) -> dict[str, Any]:
    return {"schema": _SCHEMA, "error": message, "products": [], "product_count": 0}


# Self-register on import.
register(ProductDocumentViewer())
