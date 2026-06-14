"""Invoices viewer — the agro_erp supply-invoice line items (Phase 3).

A :class:`DatumDocTool` subclass: the base owns the catalog-read/resolve/envelope
preamble; this supplies only the projection. Reads the ``invoices`` doc (``4-6-N``
vg-6 rows), resolves the invoice / product / supplier lcl-node references to names via
the shared :class:`NameIndex`, and decodes the nominal weight/cost — emitting a
declarative ``record_table`` payload the shared JS container renderer paints (no
per-tool JS). The invoice name embeds its date (MMDDYYYY), so no HOPS-UTC decode is
needed for a legible line.
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    Markers,
    cached_index,
    decode_label,
    iter_marker_pairs,
)

from ._archetype import find_named_document
from ._contract import DatumDocTool
from ._registry import register
from ._shared.utilities import as_text as _as_text
from ._shared.utilities import row_head as _row_head


class InvoicesViewer(DatumDocTool):
    tool_id = "invoices"
    label = "Invoices"
    summary = "Supply invoice line items — product, supplier, weight and cost resolved from the sandbox."
    schema = "mycite.v2.portal.workbench.tool.invoices.v1"
    canonical_name = "invoices"
    container = "record_table"
    applies_to_archetype: tuple[str, ...] = ("mycite.v2.datum.agro_erp.invoices.v1",)

    def empty_body(self) -> dict[str, Any]:
        return {"container": self.container, "columns": [], "rows": [], "row_count": 0}

    def shape_payload(self, *, doc: Any, docs: list[Any], sandbox: str, datum_address: str) -> dict[str, Any]:
        lcl = cached_index(find_named_document(docs, sandbox=sandbox, name="lcl"))
        rows: list[dict[str, Any]] = []
        for row in getattr(doc, "rows", ()) or ():
            if not _as_text(row.datum_address).startswith("4-6-"):
                continue
            head = _row_head(row)
            lcl_refs: list[str] = []
            nominals: list[str] = []
            for marker, value in iter_marker_pairs(head):
                if marker == Markers.LCL_ID:
                    lcl_refs.append(_as_text(value))
                elif marker == Markers.NOMINAL:
                    nominals.append(decode_label(value))
            # head order (ledger): invoice_node, product_node, supplier_node.
            invoice, product, supplier = [*lcl_refs, "", "", ""][:3]
            weight, cost = [*nominals, "", ""][:2]
            rows.append({
                "invoice": lcl.resolve(invoice) or invoice,
                "product": lcl.resolve(product) or product,
                "supplier": lcl.resolve(supplier) or supplier,
                "weight": weight,
                "cost": cost,
            })
        return {
            "container": self.container,
            "title": "Invoices",
            "count_label": f"{len(rows)} line item{'' if len(rows) == 1 else 's'}",
            "columns": ["invoice", "product", "supplier", "weight", "cost"],
            "rows": rows,
            "row_count": len(rows),
            "empty_text": "No invoice line items.",
        }


register(InvoicesViewer())
