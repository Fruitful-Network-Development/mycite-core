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

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.lens.base import BinaryTextLens
from MyCiteV2.packages.state_machine.portal_shell.shell_schemas import (
    WORKBENCH_UI_TOOL_ROUTE,
)
from MyCiteV2.packages.tools.product_document_view import LclNameIndex

from ._registry import register

_TENANT_DEFAULT = "fnd"
_SCHEMA = "mycite.v2.portal.workbench.tool.contracts.v1"
_RF_UTC = "rf.3-1-6"
_RF_LCL_ID = "rf.3-1-5"
_RF_NOMINAL = "rf.3-1-7"
_RF_TITLE = "rf.3-1-2"
_NOMINAL_BITS = 136
_TITLE_BITS = 512
_BINARY_TEXT = BinaryTextLens()


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


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


def _find_named(docs: list[AuthoritativeDatumDocument], sandbox: str, name: str) -> AuthoritativeDatumDocument | None:
    for doc in docs:
        if _as_text(getattr(doc, "canonical_name", "")) == name:
            parts = _as_text(getattr(doc, "document_id", "")).split(".")
            if not sandbox or (len(parts) > 4 and parts[2] == sandbox):
                return doc
    return None


def _invoice_weights(invoices: AuthoritativeDatumDocument | None, lcl: LclNameIndex) -> dict[str, dict[str, Any]]:
    """invoice lcl-node -> {label, weight} from the invoices 4-6-* rows (weight = pair 4)."""
    out: dict[str, dict[str, Any]] = {}
    if invoices is None:
        return out
    for row in _rows(invoices):
        if not _as_text(row.datum_address).startswith("4-6-"):
            continue
        head = row.raw[0] if isinstance(row.raw, list) and row.raw else []
        # head: [addr, rf.3-1-5 invoice_node, rf.3-1-6 date, rf.3-1-5 product, rf.3-1-7 weight, ...]
        invoice_node = _as_text(head[2]) if len(head) > 2 else ""
        weight = ""
        markers = [(head[i], head[i + 1]) for i in range(1, len(head) - 1, 2)]
        nominals = [v for m, v in markers if _as_text(m) == _RF_NOMINAL]
        if nominals:
            weight = _BINARY_TEXT.decode(nominals[0])
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
        if authority_db_file is None:
            return _error("authority database not configured")
        try:
            store = SqliteSystemDatumStoreAdapter(authority_db_file)
            catalog = store.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id=_TENANT_DEFAULT)
            )
        except Exception as exc:
            return _error(f"datum store unavailable: {exc}")
        docs = list(getattr(catalog, "documents", ()) or ())
        sandbox = sandbox_id or "agro_erp"
        doc = next((d for d in docs if _as_text(getattr(d, "document_id", "")) == _as_text(document_id)), None)
        if doc is None:
            doc = _find_named(docs, sandbox, "contracts")
        if doc is None:
            return _error("contracts document not found")

        lcl = LclNameIndex(_find_named(docs, sandbox, "lcl"))
        invoices = _find_named(docs, sandbox, "invoices")
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
                    nominals.append(_BINARY_TEXT.decode(value))
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

        # Weight draw-down: purchased weight per invoice minus committed contract amounts.
        draw_down = []
        referenced = set(committed) | (set(inv_weights) if not contracts else set(committed))
        for node in sorted(referenced or inv_weights):
            info = inv_weights.get(node, {"label": node, "weight": 0.0})
            used = committed.get(node, 0.0)
            draw_down.append({
                "invoice": info["label"],
                "purchased_weight": info.get("weight", 0.0),
                "committed": used,
                "remaining": round(info.get("weight", 0.0) - used, 6),
                "over_committed": used > info.get("weight", 0.0),
            })

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
