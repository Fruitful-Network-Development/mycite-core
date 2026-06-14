"""Reconcile the agro_erp lcl entity branches + add operator-role nodes (Phase 1b).

Phase 0 verification found the live invoices/contacts docs reference lcl nodes that were
never persisted (finding F1): the contact branch ``1-1-4`` (+ supplier nodes), the invoice
branch ``1-4`` (+ one node per invoice line), and the contract type ``1-5``. The live lcl
top-level is only ``1-1``/``1-2``/``1-3`` — so the SAMRAS contiguous-ordinal rule also
BLOCKS adding the operator-role branch at ``1-6`` until ``1-4``/``1-5`` exist.

This script does both in one surgical, additive, idempotent mutation:

1. **Reconcile** — define exactly the contact/invoice/contract entity nodes the live
   consumer docs already reference, taking their faithful node→label→marker from the
   ledger's own build (the authoritative generator), filtered to the ``1-1-4``/``1-4``/
   ``1-5`` subtrees. The ledger's re-minted ``1-3-1-*`` product leaves are EXCLUDED (they
   conflict with product_profiles' own leaves — Phase 0 finding F3). After this, the
   invoices/contacts refs resolve (F1 fixed) and Phase 3's viewers are unblocked.
2. **Roles** — mint the operator-role branch ``1-6`` ("operator_roles") with children
   ``1-6-1`` farm_operator / ``1-6-2`` selling_entity / ``1-6-3`` employer /
   ``1-6-4`` product_handler (now contiguous since ``1-4``/``1-5`` exist).

Then recompute the anchor ``1-1-5`` lcl-SAMRAS magnitude over the extended node set.
Touches ONLY anchor + lcl; the invoices/contacts/contracts docs are left byte-identical
(their refs simply resolve now). Does NOT re-run any ingest. Reuse-by-title → re-run is a
no-op. Discipline: copy → dry-run → verify → apply live with a timestamped backup.

Usage:
    python -m MyCiteV2.scripts.reconcile_agro_erp_lcl_entities --authority-db DB [--dry-run]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.refs import is_node_ref_marker
from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.scripts import ingest_agro_erp_ledger as ledger
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    ANCHOR_LCL_SAMRAS,
    RF_TXA_ID,
    SANDBOX,
    TENANT,
    LclBuilder,
    _as_rows,
    _build_magnitude_bitstream,
    _finalize,
    _prefix_closure,
    _rebuild_document,
    _row,
    _upsert_documents_row,
)

ROLE_PARENT_LABEL = "operator_roles"
ROLE_LABELS = ("farm_operator", "selling_entity", "employer", "product_handler")
EXPECT_PARENT = "1-6"
EXPECT_ROLES = ("1-6-1", "1-6-2", "1-6-3", "1-6-4")
# Entity subtrees to reconcile (NOT the ledger's re-minted 1-3-1-* product leaves).
_RECON_ROOTS = ("1-1-4", "1-4", "1-5")
# Docs that must stay byte-identical (we only ever write anchor + lcl).
UNTOUCHED = ("txa", "product_profiles", "farm_profile", "contacts", "invoices", "contracts")


def _in_recon_subtree(node: str) -> bool:
    return any(node == r or node.startswith(r + "-") for r in _RECON_ROOTS)


def _node_labels(doc: AuthoritativeDatumDocument) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in _as_rows(doc):
        if str(r.datum_address).startswith("4-2-") and len(r.raw[0]) >= 3:
            out[str(r.raw[0][2])] = str(r.raw[1][0]) if len(r.raw) > 1 and r.raw[1] else ""
    return out


def _dangling_entity_refs(doc: AuthoritativeDatumDocument, defined: set[str]) -> set[str]:
    out: set[str] = set()
    for r in _as_rows(doc):
        head = r.raw[0]
        for i in range(1, len(head) - 1, 2):
            if is_node_ref_marker(str(head[i])):
                v = str(head[i + 1])
                if _in_recon_subtree(v) and v != "0" and v not in defined:
                    out.add(v)
    return out


@dataclasses.dataclass
class Plan:
    docs: dict[str, AuthoritativeDatumDocument]
    hashes: dict[str, str]
    prior_ids: dict[str, str]
    untouched_ids: dict[str, str]
    reconciled: list[tuple[str, str]]
    role_nodes: list[str]
    report: dict


def build(store: SqliteSystemDatumStoreAdapter) -> Plan:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
    for name in ("anchor", "lcl", "invoices", "contacts"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found in catalog")

    live_lcl_nodes = set(_node_labels(live["lcl"]))

    # --- faithful entity node→label→marker from the ledger's own build --------
    ledger_result = ledger.build(store)
    recon: list[tuple[str, str, str]] = []  # (node, label, marker) in ledger row order
    for r in _as_rows(ledger_result.docs["lcl"]):
        if not str(r.datum_address).startswith("4-2-") or len(r.raw[0]) < 3:
            continue
        head = r.raw[0]
        node, marker = str(head[2]), str(head[1])
        if node in live_lcl_nodes or not _in_recon_subtree(node):
            continue
        label = str(r.raw[1][0]) if len(r.raw) > 1 and r.raw[1] else ""
        recon.append((node, label, marker))

    # --- merge ONLY those entity nodes into the LIVE lcl (fresh 4-2 keys) -----
    lb = LclBuilder(_as_rows(live["lcl"]))
    for node, label, marker in recon:
        lb.ensure(node, label, marker)
    reconciled = [(n, lbl) for n, lbl, _ in recon]

    # --- operator-role branch (now contiguous: 1-4/1-5 exist) ----------------
    parent = lb.mint_child("1", ROLE_PARENT_LABEL, RF_TXA_ID)
    if parent != EXPECT_PARENT:
        raise SystemExit(f"expected role parent {EXPECT_PARENT}, minted {parent} — top-level lcl not contiguous after reconcile; aborting")
    role_nodes = [lb.mint_child(parent, lbl, RF_TXA_ID) for lbl in ROLE_LABELS]
    if tuple(role_nodes) != EXPECT_ROLES:
        raise SystemExit(f"expected role nodes {EXPECT_ROLES}, minted {tuple(role_nodes)} — aborting")

    new_lcl, lcl_hash = _rebuild_document(existing=live["lcl"], overlay=lb.overlay, name="lcl")

    # --- anchor: recompute the 1-1-5 lcl-SAMRAS row, every other row untouched
    lcl_samras_bits = _build_magnitude_bitstream(lb.node_set)
    anchor_rows = [
        _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_samras_bits], ["lcl-SAMRAS"]])
        if r.datum_address == ANCHOR_LCL_SAMRAS else r
        for r in _as_rows(live["anchor"])
    ]
    new_anchor, anchor_hash = _finalize(dataclasses.replace(live["anchor"], rows=tuple(anchor_rows)), "anchor")

    report = {
        "entity_nodes_reconciled": len(recon),
        "contact_nodes": [n for n, _, _ in recon if n.startswith("1-1-4")],
        "invoice_nodes": len([n for n, _, _ in recon if n == "1-4" or n.startswith("1-4-")]),
        "contract_nodes": [n for n, _, _ in recon if n.startswith("1-5")],
        "role_nodes": role_nodes,
        "lcl_rows_added": len(lb.overlay),
        "lcl_node_count": len(lb.node_set),
        "lcl_closure": len(_prefix_closure(lb.node_set)),
    }
    return Plan(
        docs={"anchor": new_anchor, "lcl": new_lcl},
        hashes={"anchor": anchor_hash, "lcl": lcl_hash},
        prior_ids={"anchor": live["anchor"].document_id, "lcl": live["lcl"].document_id},
        untouched_ids={n: live[n].document_id for n in UNTOUCHED if n in live},
        reconciled=reconciled,
        role_nodes=role_nodes,
        report=report,
    )


def _print_report(plan: Plan, *, dry_run: bool) -> None:
    r = plan.report
    print("\n========== LCL ENTITY RECONCILE + ROLES PLAN ==========")
    print(f"entity nodes reconciled : {r['entity_nodes_reconciled']}  "
          f"(contacts={len(r['contact_nodes'])}, invoices={r['invoice_nodes']}, contract={len(r['contract_nodes'])})")
    print(f"role nodes              : {dict(zip(ROLE_LABELS, r['role_nodes'], strict=True))}")
    print(f"lcl rows added          : {r['lcl_rows_added']}  (node_count={r['lcl_node_count']}, closure={r['lcl_closure']})")
    for name in ("anchor", "lcl"):
        d = plan.docs[name]
        tag = "(unchanged)" if d.document_id == plan.prior_ids[name] else "(CHANGED)"
        print(f"  {name:13} rows={len(d.rows):5}  …{d.document_id.split('.')[-1][:14]}  {tag}")
    print("=======================================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")


def _verify(authority_db: Path, plan: Plan) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    docs = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    failures: list[str] = []

    for name, prior in plan.untouched_ids.items():
        cur = docs.get(name)
        if cur is None:
            failures.append(f"{name} disappeared")
        elif cur.document_id != prior:
            failures.append(f"{name} CHANGED unexpectedly")

    lcl = docs.get("lcl")
    lcl_nodes = set(_node_labels(lcl)) if lcl else set()
    for node in (*[n for n, _ in plan.reconciled], EXPECT_PARENT, *EXPECT_ROLES):
        if node not in lcl_nodes:
            failures.append(f"node {node} not defined in lcl after write")

    # the previously-dangling invoices/contacts refs must now all resolve
    for name in ("invoices", "contacts"):
        d = docs.get(name)
        if d is not None:
            remaining = _dangling_entity_refs(d, lcl_nodes)
            if remaining:
                failures.append(f"{name} still has {len(remaining)} dangling entity refs: {sorted(remaining)[:5]}")

    # lcl SAMRAS denoted == defined (closure intact)
    anchor = docs.get("anchor")
    samras_row = next((r for r in _as_rows(anchor) if r.datum_address == ANCHOR_LCL_SAMRAS), None) if anchor else None
    denoted = set(decode_canonical_bitstream(str(samras_row.raw[0][2])).addresses) if samras_row else set()
    if denoted != lcl_nodes:
        failures.append(f"lcl SAMRAS denoted({len(denoted)}) != lcl defined({len(lcl_nodes)})")
    for node in (EXPECT_PARENT, *EXPECT_ROLES):
        if node not in denoted:
            failures.append(f"role node {node} not denoted in lcl-SAMRAS")

    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures))
    print(f"[verify] PASSED — {len(plan.reconciled)} entity nodes + {len(EXPECT_ROLES)} roles live; "
          f"invoices/contacts refs resolve; {len(plan.untouched_ids)} sibling docs byte-identical")


def run(*, authority_db: Path, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    plan = build(store)
    _print_report(plan, dry_run=dry_run)
    if dry_run:
        return {"status": "dry_run", **plan.report}

    if plan.docs["lcl"].document_id == plan.prior_ids["lcl"]:
        print("[skip] entity + role nodes already present (reuse-by-title) — nothing to write")
        return {"status": "noop", **plan.report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-lclrecon-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")

    for name in ("anchor", "lcl"):
        doc = plan.docs[name]
        store.replace_single_document_efficient(
            tenant_id=TENANT, prior_document_id=plan.prior_ids[name], updated_document=doc
        )
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id,
                              version_hash=plan.hashes[name], is_anchor=(name == "anchor"))
        print(f"[write] {name} → …{doc.document_id.split('.')[-1][:14]}")

    _verify(authority_db, plan)
    return {"status": "applied", "backup": str(backup), **plan.report,
            "document_ids": {n: plan.docs[n].document_id for n in ("anchor", "lcl")}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
