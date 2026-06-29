"""Record Viewer — shared base for agro_erp record tables (invoices, contracts).

A *record* doc holds same-shaped entries: an ordered list of ``(marker, magnitude)`` head
pairs. This base projects them into a declarative ``record_table`` from one positional
``column_spec`` — each ``(col, kind)`` maps the head pair at that position, resolving lcl/txa
node refs to names, decoding nominals, and surfacing the event-type. :class:`InvoiceViewer`
and :class:`ContractViewer` are thin subclasses (spec + row-prefix + labels); the contract
viewer adds an invoice weight draw-down as an extra table.

Built on :class:`DatumDocTool` (canonical-name doc resolution + standard envelope); the only
subclass surface is the declarative spec, so a new record type is a few lines, no new walk.
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import (
    cached_index,
    decode_label,
    iter_marker_pairs,
)

from ._archetype import find_named_document
from ._contract import DatumDocTool
from ._shared.utilities import as_text as _as_text
from ._shared.utilities import row_head as _row_head

# column kinds
LCL = "lcl"        # lcl node ref → name via lcl NameIndex
TXA = "txa"        # txa node ref → name via txa NameIndex
NOMINAL = "nominal"  # 136-bit ASCII nominal (weight/cost/amount) → text
DATE = "date"      # HOPS-UTC token (raw passthrough)
EVENT = "event"    # lcl event_classification ref → name via lcl NameIndex


class RecordViewerBase(DatumDocTool):
    """Project a record doc's same-shaped entries into a ``record_table``."""

    container = "record_table"
    row_prefix: str = ""
    # Ordered spec, one entry per head pair: (column_name, kind).
    column_spec: tuple[tuple[str, str], ...] = ()
    # Columns to show, in order (default: every spec column).
    display_columns: tuple[str, ...] = ()
    title: str = "Records"
    noun: str = "record"

    def empty_body(self) -> dict[str, Any]:
        return {"container": self.container, "columns": [], "rows": [], "row_count": 0}

    @staticmethod
    def _resolve(kind: str, value: Any, lcl: Any, txa: Any) -> str:
        if kind in (LCL, EVENT):
            v = _as_text(value)
            return lcl.resolve(v) or v
        if kind == TXA:
            v = _as_text(value)
            return txa.resolve(v) or v
        if kind == NOMINAL:
            return decode_label(value)
        return _as_text(value)

    def project_rows(self, *, doc: Any, lcl: Any, txa: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in getattr(doc, "rows", ()) or ():
            if not _as_text(row.datum_address).startswith(self.row_prefix):
                continue
            rec: dict[str, Any] = {}
            # strict=False: a short/malformed row simply yields fewer columns (no raise).
            for (col, kind), (_marker, value) in zip(self.column_spec, iter_marker_pairs(_row_head(row)), strict=False):
                rec[col] = self._resolve(kind, value, lcl, txa)
            rows.append(rec)
        return rows

    def shape_payload(self, *, doc: Any, docs: list[Any], sandbox: str, datum_address: str) -> dict[str, Any]:
        lcl = cached_index(find_named_document(docs, sandbox=sandbox, name="lcl"))
        txa = cached_index(find_named_document(docs, sandbox=sandbox, name="txa"))
        rows = self.project_rows(doc=doc, lcl=lcl, txa=txa)
        cols = list(self.display_columns) or [c for c, _ in self.column_spec]
        return {
            "container": self.container,
            "title": self.title,
            "count_label": f"{len(rows)} {self.noun}{'' if len(rows) == 1 else 's'}",
            "columns": cols,
            "rows": rows,
            "row_count": len(rows),
            "empty_text": f"No {self.noun}s.",
        }
