"""Contracts viewer + create-builder for agro_erp.

Views the agro_erp ``contracts`` document (archetype ``4-5-N = [date, invoice_id,
plot_id, amount, cost]``): resolves invoice_id / plot_id references to names via the
``lcl`` index, decodes the nominal amount/cost, and computes the weight draw-down of
contracts against their invoices' purchased weight. Plot ids reference the plot nodes
migrated into farm_profile (TASK-006). See plans/TASK-007-contracts-tool.md.

Eligibility is by the contracts schema token (TASK-008 derive_document_archetypes).
``build_contract_row`` is the pure unit a create-form / ingest mints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.core.datum_ops.datum_resolve import NameIndex, cached_index, decode_label
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)

from ._archetype import find_named_document, read_sandbox_catalog, resolve_tool_document
from ._registry import register
from ._shared.utilities import as_text as _as_text

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.contracts.v1"
_RF_UTC = "rf.3-1-6"
_RF_LCL_ID = "rf.3-1-5"
_RF_NOMINAL = "rf.3-1-7"
_RF_TITLE = "rf.3-1-2"
_NOMINAL_BITS = 136
_TITLE_BITS = 512


def _error(message: str) -> dict[str, Any]:
    return {"schema": _SCHEMA, "error": message, "contracts": [], "draw_down": [], "contract_count": 0}


def _rows(document: AuthoritativeDatumDocument) -> list[AuthoritativeDatumDocumentRow]:
    out = []
    for r in getattr(document, "rows", ()) or ():
        out.append(r if isinstance(r, AuthoritativeDatumDocumentRow) else AuthoritativeDatumDocumentRow.from_dict(r))
    return out


def _encode_bits(label: str, *, bits: int) -> str:
    raw = "".join(format(b, "08b") for b in label.encode("ascii"))
    if len(raw) > bits:
        raise ValueError(f"value {label!r} exceeds {bits} bits")
    return raw.ljust(bits, "0")


def build_contract_row(
    addr: str,
    *,
    hops_date: str,
    invoice_node: str,
    plot_node: str,
    amount: str,
    cost: str,
    label: str,
) -> AuthoritativeDatumDocumentRow:
    """Pure builder for a contract datum (vg=5: date, invoice_id, plot_id, amount, cost).

    ``hops_date`` is a pre-encoded HOPS-UTC token (caller computes it from the chronology
    authority). The remaining fields are an lcl invoice node, an lcl plot node (from the
    migrated plots), and nominal amount/cost strings. This is the unit a create-form mints.
    """
    head = [
        addr,
        _RF_UTC, hops_date,
        _RF_LCL_ID, invoice_node,
        _RF_LCL_ID, plot_node,
        _RF_NOMINAL, _encode_bits(amount, bits=_NOMINAL_BITS),
        _RF_NOMINAL, _encode_bits(cost, bits=_NOMINAL_BITS),
    ]
    return AuthoritativeDatumDocumentRow(datum_address=addr, raw=[head, [label]])


def _parse_weight(text: str) -> float:
    """Best-effort numeric prefix of a weight/amount string ('25 lbs' -> 25.0)."""
    num = ""
    for ch in text.strip():
        if ch.isdigit() or ch in ".-":
            num += ch
        elif num:
            break
    try:
        return float(num) if num else 0.0
    except ValueError:
        return 0.0


def _draw_down(inv_weights: dict[str, dict[str, Any]], committed: dict[str, float]) -> list[dict[str, Any]]:
    """Per-invoice weight draw-down: purchased weight minus committed contract amounts.

    Iterates the UNION of invoices-with-weight and committed nodes, so an invoice with
    purchased weight but no contract stays visible (with full remaining capacity) once
    any contract exists — it is not dropped just because nothing is committed against it.
    """
    rows: list[dict[str, Any]] = []
    for node in sorted(set(inv_weights) | set(committed)):
        info = inv_weights.get(node, {"label": node, "weight": 0.0})
        used = committed.get(node, 0.0)
        weight = info.get("weight", 0.0)
        rows.append({
            "invoice": info["label"],
            "purchased_weight": weight,
            "committed": used,
            "remaining": round(weight - used, 6),
            "over_committed": used > weight,
        })
    return rows


def _invoice_weights(invoices: AuthoritativeDatumDocument | None, lcl: NameIndex) -> dict[str, dict[str, Any]]:
    """invoice lcl-node -> {label, weight} from the invoices 4-6-* rows.

    Marker-driven (order-independent): the invoice node is the FIRST rf.3-1-5 value
    and the weight is the FIRST rf.3-1-7 nominal, scanned as (marker, value) pairs —
    not read from a fixed head position.
    """
    out: dict[str, dict[str, Any]] = {}
    if invoices is None:
        return out
    for row in _rows(invoices):
        if not _as_text(row.datum_address).startswith("4-6-"):
            continue
        head = row.raw[0] if isinstance(row.raw, list) and row.raw else []
        markers = [(_as_text(head[i]), head[i + 1]) for i in range(1, len(head) - 1, 2)]
        invoice_node = next((_as_text(v) for m, v in markers if m == _RF_LCL_ID), "")
        nominals = [v for m, v in markers if m == _RF_NOMINAL]
        weight = decode_label(nominals[0]) if nominals else ""
        if invoice_node:
            out[invoice_node] = {"label": lcl.resolve(invoice_node) or invoice_node, "weight": _parse_weight(weight), "weight_text": weight}
    return out


class ContractsTool:
    """View + (build) contracts binding farm plots to invoices, with weight draw-down."""

    tool_id = "contracts"
    label = "Contracts"
    summary = "Contracts binding farm plots to invoices, with weight draw-down."
    route = WORKBENCH_UI_TOOL_ROUTE
    applies_to_archetype: tuple[str, ...] = ("mycite.v2.datum.agro_erp.contracts.v1",)
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
        sandbox = sandbox_id or "agro_erp"
        # Resolve the contracts doc by archetype, not by trusting the selected
        # document_id — the workbench auto-selects the first sandbox doc, which would
        # otherwise be rendered as an empty contracts view. See _archetype.
        doc = resolve_tool_document(
            docs, tool=self, sandbox=sandbox, document_id=document_id, canonical_name="contracts"
        )
        if doc is None:
            return _error("contracts document not found")

        lcl = cached_index(find_named_document(docs, sandbox=sandbox, name="lcl"))
        invoices = find_named_document(docs, sandbox=sandbox, name="invoices")
        inv_weights = _invoice_weights(invoices, lcl)

        contracts: list[dict[str, Any]] = []
        committed: dict[str, float] = {}
        for row in _rows(doc):
            if not _as_text(row.datum_address).startswith("4-5-"):
                continue
            head = row.raw[0] if isinstance(row.raw, list) and row.raw else []
            date = invoice_node = plot_node = ""
            nominals: list[str] = []
            for i in range(1, len(head) - 1, 2):
                marker, value = _as_text(head[i]), head[i + 1]
                if marker == _RF_UTC and not date:
                    date = _as_text(value)
                elif marker == _RF_LCL_ID and not invoice_node:
                    invoice_node = _as_text(value)
                elif marker == _RF_LCL_ID:
                    plot_node = _as_text(value)
                elif marker == _RF_NOMINAL:
                    nominals.append(decode_label(value))
            amount, cost = [*nominals, "", ""][:2]
            committed[invoice_node] = committed.get(invoice_node, 0.0) + _parse_weight(amount)
            contracts.append({
                "datum_address": row.datum_address,
                "date": date,
                "invoice": lcl.resolve(invoice_node) or invoice_node,
                "plot": lcl.resolve(plot_node) or plot_node,
                "amount": amount,
                "cost": cost,
            })

        draw_down = _draw_down(inv_weights, committed)

        return {
            "schema": _SCHEMA,
            "sandbox_id": sandbox,
            "document_id": _as_text(doc.document_id),
            "archetype": "4-5-N = [date, invoice_id, plot_id, amount, cost]",
            "contract_count": len(contracts),
            "contracts": contracts,
            "draw_down": draw_down,
        }


# Self-register on import.
register(ContractsTool())
