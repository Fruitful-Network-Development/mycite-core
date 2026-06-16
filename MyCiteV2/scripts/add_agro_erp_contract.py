"""Contracts builder — mint a contract row into the agro_erp contracts doc (Phase 4).

The write-path proof for the agronomics group: takes (invoice, plot, amount, cost, date),
resolves the invoice/plot lcl nodes, ENFORCES the weight draw-down invariant (the sum of
contract amounts against an invoice may not exceed that invoice's purchased weight), and
appends a ``4-5-N`` contract row via the pure ``contracts_tool.build_contract_row`` unit.
Writes only the contracts doc (anchor/lcl untouched — contracts reference existing nodes).

Idempotent-ish: refuses to add a byte-identical duplicate contract. Discipline: dry-run →
apply with a timestamped backup → post-write verify. Mirrors the ingest scripts.

Usage:
    python -m MyCiteV2.scripts.add_agro_erp_contract --authority-db DB \\
        --invoice 1-4-1 --plot 1-2-2 --amount "10 lbs" --cost "$40.00" --date 03-01-2025 [--dry-run]
    (invoice/plot may be a node address OR a defined name.)
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.datum_resolve import cached_index, decode_label
from MyCiteV2.packages.core.datum_ops.refs import _head, _is_definition_head
from MyCiteV2.packages.core.structures.samras.structure import as_text
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.packages.tools.contracts_tool import (
    _invoice_weights,
    _parse_weight,
    build_contract_row,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    ANCHOR_TIME_PRIMITIVE,
    SANDBOX,
    TENANT,
    _as_rows,
    _finalize,
    _upsert_documents_row,
    build_chronology_authority,
    encode_utc_datetime_as_hops,
    schema_from_anchor_payload,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    _row as _ledger_row,  # noqa: F401  (kept for parity)
)

_RF_LCL_ID = "rf.3-1-5"
_RF_NOMINAL = "rf.3-1-7"
_RF_UTC = "rf.3-1-6"


def _name_to_node(doc: AuthoritativeDatumDocument) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in _as_rows(doc):
        head = _head(r.raw)
        if head is None or not _is_definition_head(head):
            continue
        node = as_text(head[2])
        label = as_text(r.raw[1][0]) if len(r.raw) > 1 and r.raw[1] else ""
        if label:
            out.setdefault(label.lower(), node)
    return out


def _resolve(token: str, name_to_node: dict[str, str], defined: set[str], *, kind: str) -> str:
    t = token.strip()
    if t in defined:
        return t
    node = name_to_node.get(t.lower())
    if node:
        return node
    raise SystemExit(f"{kind} {token!r} is neither a defined lcl node nor a known name")


@dataclasses.dataclass
class Plan:
    doc: AuthoritativeDatumDocument
    prior_id: str
    version_hash: str
    report: dict


def _unit_of(text: str) -> str:
    """Trailing alphabetic unit token of a weight string ('10 lbs' -> 'lbs', '$40' -> '')."""
    m = re.search(r"[A-Za-z]+", text or "")
    return m.group(0).lower() if m else ""


def build(store, *, invoice: str, plot: str, amount: str, cost: str, date: str) -> Plan:
    # Normalize the free-text amount/cost so a re-run with trivially-different whitespace
    # dedups against the stored row (the dedup below compares against decode_label values).
    amount, cost = amount.strip(), cost.strip()
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    cts_anchor = None
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
        elif ".cts_gis.anchor." in d.document_id:
            cts_anchor = d
    for name in ("anchor", "lcl", "contracts", "invoices"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found")
    if cts_anchor is None:
        raise SystemExit("cts_gis anchor (chronology source) not found")

    lcl_idx = cached_index(live["lcl"])
    n2n = _name_to_node(live["lcl"])
    defined = {as_text(_head(r.raw)[2]) for r in _as_rows(live["lcl"]) if _head(r.raw) and _is_definition_head(_head(r.raw))}
    invoice_node = _resolve(invoice, n2n, defined, kind="invoice")
    plot_node = _resolve(plot, n2n, defined, kind="plot")

    # --- draw-down invariant -------------------------------------------------
    inv_weights = _invoice_weights(live["invoices"], lcl_idx)
    info = inv_weights.get(invoice_node)
    if info is None:
        raise SystemExit(f"invoice node {invoice_node} has no purchased weight in invoices doc")
    committed = 0.0
    existing = [r for r in _as_rows(live["contracts"]) if as_text(r.datum_address).startswith("4-5-")]
    for r in existing:
        head = r.raw[0] if isinstance(r.raw, list) and r.raw else []
        refs = [as_text(head[i + 1]) for i in range(1, len(head) - 1, 2) if as_text(head[i]) == _RF_LCL_ID]
        if refs and refs[0] == invoice_node:
            # amount is the first nominal; reuse the viewer's parse
            noms = [decode_label(head[i + 1]) for i in range(1, len(head) - 1, 2) if as_text(head[i]) == _RF_NOMINAL]
            committed += _parse_weight(noms[0]) if noms else 0.0
    new_amt = _parse_weight(amount)
    purchased = info["weight"]
    # The draw-down arithmetic is unit-blind (_parse_weight strips to a numeric prefix),
    # so refuse a contract whose unit differs from the invoice's purchased-weight unit
    # rather than silently comparing e.g. 90 kg against 100 lbs.
    inv_unit, amt_unit = _unit_of(info.get("weight_text", "")), _unit_of(amount)
    if inv_unit and amt_unit and inv_unit != amt_unit:
        raise SystemExit(
            f"unit mismatch: invoice {info['label']} purchased in {inv_unit!r} but contract "
            f"amount is in {amt_unit!r}; the draw-down is unit-blind — supply the amount in "
            f"the invoice's units ({inv_unit})"
        )
    if committed + new_amt > purchased + 1e-9:
        raise SystemExit(
            f"draw-down exceeded: invoice {info['label']} purchased {purchased}, "
            f"already committed {committed}, +{new_amt} would over-commit"
        )

    # --- mint the contract row -----------------------------------------------
    cts_rows = {r.datum_address: r.raw for r in _as_rows(cts_anchor)}
    cts_time_row = cts_rows.get("1-1-5")
    if not (cts_time_row and isinstance(cts_time_row[0], list) and len(cts_time_row[0]) > 2):
        raise SystemExit("cts_gis anchor missing the 1-1-5 chronology row (cannot build time schema)")
    schema_payload = schema_from_anchor_payload(
        {"1-1-1": [["1-1-1", ANCHOR_TIME_PRIMITIVE, str(cts_time_row[0][2])], ["HOPS-chronological"]]}
    )
    if not schema_payload.get("ok"):
        raise SystemExit(f"cts time schema decode failed: {schema_payload.get('error')}")
    chrono = build_chronology_authority(
        schema_payload=schema_payload,
        quadrennium_payload={"3-1-1": [["3-1-1", "~", "0"], ["quadrennium"]]},
        cosmological_prefix=(0, 0),
    )
    mm, dd, yyyy = (int(x) for x in date.split("-"))
    hops_date = encode_utc_datetime_as_hops(datetime(yyyy, mm, dd, tzinfo=UTC), authority=chrono)

    # Dedup: a logically-identical (date, invoice, plot, amount, cost) contract already
    # present → no-op (returning the unchanged doc keeps document_id == prior_id, which
    # run() reports as a noop). Without this the always-incrementing 4-5-N address makes
    # every re-run mint a duplicate that double-counts the draw-down.
    new_sig = (hops_date, invoice_node, plot_node, amount, cost)
    for r in existing:
        head = r.raw[0] if isinstance(r.raw, list) and r.raw else []
        pairs = [(as_text(head[i]), head[i + 1]) for i in range(1, len(head) - 1, 2)]
        refs = [as_text(v) for m, v in pairs if m == _RF_LCL_ID]
        # Strip decoded nominals so the dedup matches the now-normalized amount/cost
        # inputs (a re-run with trailing whitespace must still be detected as a duplicate).
        noms = [decode_label(v).strip() for m, v in pairs if m == _RF_NOMINAL]
        dates = [as_text(v) for m, v in pairs if m == _RF_UTC]
        sig = ([*dates, ""][0], [*refs, "", ""][0], [*refs, "", ""][1],
               [*noms, "", ""][0], [*noms, "", ""][1])
        if sig == new_sig:
            report = {"contract_addr": as_text(r.datum_address), "duplicate": True,
                      "invoice": f"{invoice_node} ({info['label']})", "plot": plot_node,
                      "amount": amount, "cost": cost, "date": date, "contracts_rows": len(existing)}
            return Plan(doc=live["contracts"], prior_id=live["contracts"].document_id,
                        version_hash="", report=report)

    next_n = 1 + max((int(as_text(r.datum_address).split("-")[2]) for r in existing), default=0)
    addr = f"4-5-{next_n}"
    label = f"{lcl_idx.resolve(invoice_node) or invoice_node}__{lcl_idx.resolve(plot_node) or plot_node}"
    new_row = build_contract_row(
        addr, hops_date=hops_date, invoice_node=invoice_node, plot_node=plot_node,
        amount=amount, cost=cost, label=label,
    )
    rows = [*_as_rows(live["contracts"]), new_row]
    new_doc, version_hash = _finalize(dataclasses.replace(live["contracts"], rows=tuple(rows)), "contracts")

    report = {
        "contract_addr": addr, "label": label,
        "invoice": f"{invoice_node} ({info['label']})", "plot": plot_node,
        "amount": amount, "cost": cost, "date": date,
        "invoice_purchased": purchased, "committed_before": committed,
        "committed_after": committed + new_amt, "remaining_after": round(purchased - committed - new_amt, 6),
        "contracts_rows": len(rows),
    }
    return Plan(doc=new_doc, prior_id=live["contracts"].document_id, version_hash=version_hash, report=report)


def run(*, authority_db: Path, dry_run: bool, **kw) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    plan = build(store, **kw)
    print("\n============ CONTRACT BUILD PLAN ============")
    for k, v in plan.report.items():
        print(f"  {k:18}: {v}")
    print("=============================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")
        return {"status": "dry_run", **plan.report}
    if plan.doc.document_id == plan.prior_id:
        print("[skip] identical contract already present")
        return {"status": "noop", **plan.report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-contract-{stamp}.bak")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=plan.prior_id, updated_document=plan.doc)
    _upsert_documents_row(authority_db, name="contracts", document_id=plan.doc.document_id, version_hash=plan.version_hash, is_anchor=False)
    print(f"[write] contracts → …{plan.doc.document_id.split('.')[-1][:14]}")
    # verify the row is present
    store2 = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    cat = store2.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    c = next(d for d in cat.documents if d.canonical_name == "contracts" and f".{SANDBOX}." in d.document_id)
    if not any(as_text(r.datum_address) == plan.report["contract_addr"] for r in c.rows):
        raise SystemExit("POST-WRITE VERIFY FAILED: contract row absent")
    print("[verify] PASSED — contract row live")
    return {"status": "applied", "backup": str(backup), **plan.report, "document_id": plan.doc.document_id}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--invoice", required=True, help="lcl invoice node (1-4-N) or name")
    ap.add_argument("--plot", required=True, help="lcl plot node (1-2-N) or name")
    ap.add_argument("--amount", required=True, help="contract weight, e.g. '10 lbs'")
    ap.add_argument("--cost", required=True, help="contract cost, e.g. '$40.00'")
    ap.add_argument("--date", required=True, help="MM-DD-YYYY")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, dry_run=args.dry_run,
                 invoice=args.invoice, plot=args.plot, amount=args.amount, cost=args.cost, date=args.date)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
