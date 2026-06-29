#!/usr/bin/env python3
"""Restructure the agro_erp **lcl** taxonomy into entity / land / classification.

The live lcl SAMRAS tree grew an ad-hoc 7-branch shape (``1-1`` entity / ``1-2`` land /
``1-3`` product / ``1-4`` invoice / ``1-5`` contract / ``1-6`` operator_roles / ``1-7``
equipment). The operator re-organized it into three semantic domains:

    entity         — employee / objects / livestock / contacts / product_type / records
    land           — parcel / field / structure / plot
    classification — product_classification / event_classification / operator_classification

Because the data is MOS-database-native, this script edits the datum documents in place:

  1. Re-authors the lcl node-definition block (``4-2-*``) to the NEW structural tree
     (:data:`NEW_TREE`), flagging the four instance-container nodes with the new
     ``rf.3-1-8`` VIEW marker (product / invoice / contract / contacts) so the
     ``local_domain`` tool can expand them into record tables.
  2. CARRIES every dynamically-minted instance leaf (supplier / invoice-line / product-SKU /
     animal / equipment / parcel / plot node) to its new address via :data:`STRUCT_REMAP`
     (longest-prefix substitution over the live node set).
  3. Recompiles the anchor ``1-1-5`` lcl-SAMRAS magnitude over the new node set.
  4. Rewrites every consumer doc's ``rf.3-1-5`` lcl references old→new so they keep
     resolving (NameIndex is address-agnostic, but the *values* must move with the tree).

Safety mirrors reconcile_agro_erp_lcl_entities.py / ingest_agro_erp_ledger.py:
  - ``--dry-run`` (DEFAULT) prints the full remap + rewrite + dangling report, writes nothing.
  - ``--apply`` takes a timestamped ``.bak`` first, then writes and self-verifies.
  - Asserts the new map is INJECTIVE, every parent exists, child ordinals are contiguous,
    and that NO consumer ref is left dangling.

Usage::

    python -m MyCiteV2.scripts.restructure_lcl_taxonomy --authority-db DB            # dry-run
    python -m MyCiteV2.scripts.restructure_lcl_taxonomy --authority-db DB --apply    # write
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.datum_resolve import Markers
from MyCiteV2.packages.core.datum_ops.node_addrs import parse_node_addr
from MyCiteV2.packages.core.datum_ops.refs import is_node_addr_reference, is_node_ref_marker
from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    ANCHOR_LCL_SAMRAS,
    RF_TITLE,
    RF_TXA_ID,
    SANDBOX,
    TENANT,
    _as_rows,
    _build_magnitude_bitstream,
    _encode_label_bits,
    _finalize,
    _prefix_closure,
    _rebuild_document,
    _row,
    _upsert_documents_row,
)

# --------------------------------------------------------------------------- #
# Target structural tree (operator spec). (address, label, view-token | None).
# Instance leaves (supplier/invoice-line/SKU/animal/equipment/parcel/plot nodes) are
# NOT listed here — they are CARRIED from the live tree by STRUCT_REMAP.
# --------------------------------------------------------------------------- #
_V_PRODUCT, _V_INVOICE, _V_CONTRACT, _V_CONTACTS = "product", "invoice", "contract", "contacts"

NEW_TREE: tuple[tuple[str, str, str | None], ...] = (
    ("1", "trapp_family_farm_llc", None),
    # meta — SAMRAS forbids a 0-ordinal segment ("1-0" is invalid), so the empty
    # meta node is the 1-4 top-level sibling (renders after classification).
    ("1-4", "meta", None),
    # entity ----------------------------------------------------------------
    ("1-1", "entity", None),
    ("1-1-1", "employee", None),
    ("1-1-2", "objects", None),
    ("1-1-3", "livestock", None),
    ("1-1-4", "contacts", _V_CONTACTS),
    ("1-1-5", "product_type", _V_PRODUCT),
    ("1-1-6", "records", None),
    ("1-1-6-1", "invoice_instance", _V_INVOICE),
    ("1-1-6-2", "contract_instance", _V_CONTRACT),
    # land ------------------------------------------------------------------
    ("1-2", "land", None),
    ("1-2-1", "parcel", None),
    ("1-2-2", "field", None),
    ("1-2-3", "structure", None),
    ("1-2-4", "plot", None),
    # classification --------------------------------------------------------
    ("1-3", "classification", None),
    ("1-3-1", "product_classification", None),
    ("1-3-1-1", "rotation_group", None),
    ("1-3-1-1-1", "legumes", None),
    ("1-3-1-1-2", "nightshades", None),
    ("1-3-1-1-3", "brassicas", None),
    ("1-3-1-1-4", "alliums", None),
    ("1-3-1-1-5", "umbellifers", None),
    ("1-3-1-1-6", "cucurbits", None),
    ("1-3-1-1-7", "leafy_greens", None),
    ("1-3-1-1-8", "chenopods", None),
    ("1-3-1-1-9", "grasses", None),
    ("1-3-1-1-10", "mallow_family", None),
    ("1-3-1-1-11", "mint_family", None),
    ("1-3-1-1-12", "sweet_potato", None),
    ("1-3-1-1-13", "composites", None),
    ("1-3-1-1-14", "other", None),
    ("1-3-1-2", "propagule", None),
    ("1-3-1-2-1", "seed", None),
    ("1-3-1-2-2", "slip", None),
    ("1-3-1-2-3", "bulb", None),
    ("1-3-1-2-4", "root", None),
    ("1-3-1-2-5", "splice", None),
    ("1-3-1-3", "genesis", None),
    ("1-3-1-3-1", "heirloom", None),
    ("1-3-1-3-2", "f1", None),
    ("1-3-1-3-3", "gmo", None),
    ("1-3-1-4", "ownership", None),
    ("1-3-1-4-1", "open", None),
    ("1-3-1-4-2", "pbr", None),
    ("1-3-1-4-3", "t_gurt", None),
    ("1-3-1-4-4", "v_gurt", None),
    ("1-3-1-5", "raunkiaerality", None),
    ("1-3-2", "event_classification", None),
    ("1-3-2-1", "procurement", None),
    ("1-3-2-2", "divestment", None),
    ("1-3-2-3", "investment", None),
    ("1-3-2-4", "yield", None),
    ("1-3-3", "operator_classification", None),
    ("1-3-3-1", "cooperative", None),
    ("1-3-3-2", "farmers_market", None),
    ("1-3-3-3", "supplier", None),
    ("1-3-3-4", "spot_buyer", None),
    ("1-3-3-5", "peer_farm", None),
)

# Old structural node → new address. Longest-prefix match carries descendants (instance
# leaves) along. ``RETIRE`` drops the node (and any subtree); refs to it are reported as
# dangling. Unmatched live nodes map to themselves (identity) — NEW_TREE then overrides any
# that are structural, so identity is safe for the abstract roots (1-1 / 1-2 / 1-3).
RETIRE = "<retire>"
STRUCT_REMAP: dict[str, str] = {
    # entity
    "1-1-1": RETIRE,     # owner — no slot in the new entity tree
    "1-1-2": "1-1-3",    # animal → livestock (carries animal leaves)
    "1-1-3": "1-1-1",    # employee (carries any employee leaves)
    "1-1-4": "1-1-4",    # contact → contacts (carries supplier leaves)
    # land is handled specially in _new_addr_for (property→parcel; plots→plot container
    # with an ordinal shift), so no 1-2-* entries here.
    # product (split)
    "1-3": RETIRE,       # bare product container — new 1-3 is classification (NEW_TREE)
    "1-3-1": "1-1-5",    # product_type → entity.product_type (carries SKU leaves)
    "1-3-2": "1-3-1",    # product_classification → classification.product_classification
    # records
    "1-4": "1-1-6-1",    # invoice → records.invoice_instance (carries line leaves)
    "1-5": "1-1-6-2",    # contract → records.contract_instance (carries instances)
    # retired branches
    "1-6": RETIRE,       # operator_roles — superseded by 1-3-3 operator_classification
    "1-8": RETIRE,       # experimental empty event_type — superseded by 1-3-2 event_classification
    # equipment
    "1-7": "1-1-2",      # equipment → objects (carries equipment leaves)
}


# --------------------------------------------------------------------------- #
# Remap algebra
# --------------------------------------------------------------------------- #
def _longest_prefix(node: str) -> str | None:
    best: str | None = None
    for p in STRUCT_REMAP:
        if node == p or node.startswith(p + "-"):
            if best is None or len(p) > len(best):
                best = p
    return best


def _new_addr_for(node: str) -> str | None:
    """New address for a live node, or ``None`` when retired."""
    segs = node.split("-")
    # Land subtree re-parent: old land children are property (1-2-1, + parcels) and the
    # plot siblings (1-2-K, K≥2 = plot_(K-1)). property → parcel (identity prefix);
    # plots → the new plot container 1-2-4 with the ordinal shifted (1-2-K → 1-2-4-(K-1)).
    if len(segs) >= 3 and segs[0] == "1" and segs[1] == "2":
        k = int(segs[2])
        rest = "-".join(segs[3:])
        base = "1-2-1" if k == 1 else f"1-2-4-{k - 1}"
        return base + (f"-{rest}" if rest else "")
    p = _longest_prefix(node)
    if p is None:
        return node  # identity (abstract roots; NEW_TREE overrides structural collisions)
    target = STRUCT_REMAP[p]
    if target == RETIRE:
        return None
    return target + node[len(p):]


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class Plan:
    docs: dict[str, AuthoritativeDatumDocument]
    hashes: dict[str, str]
    prior_ids: dict[str, str]
    new_node_set: set[str]
    ref_map: dict[str, str]
    carried: dict[str, str]          # new_addr -> old_addr (instance leaves carried over)
    retired: list[str]
    ref_rewrites: dict[str, int]
    dangling: dict[str, list[tuple[str, str]]]
    report: dict


def _old_definitions(lcl: AuthoritativeDatumDocument) -> dict[str, tuple[str, str]]:
    """live lcl node_address -> (label, node-ref marker), from 4-2-* definition rows."""
    out: dict[str, tuple[str, str]] = {}
    for r in _as_rows(lcl):
        if not r.datum_address.startswith("4-2-"):
            continue
        head = r.raw[0]
        if len(head) < 3:
            continue
        node, marker = str(head[2]), str(head[1])
        label = str(r.raw[1][0]) if len(r.raw) > 1 and r.raw[1] else ""
        out.setdefault(node, (label, marker))
    return out


def build(store: SqliteSystemDatumStoreAdapter) -> Plan:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
    for name in ("anchor", "lcl"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found in catalog")

    old_def = _old_definitions(live["lcl"])
    old_nodes = set(old_def)

    # 1) old → new map over the LIVE node set ------------------------------------
    node_map: dict[str, str] = {}
    retired: list[str] = []
    for n in sorted(old_nodes, key=parse_node_addr):
        nn = _new_addr_for(n)
        if nn is None:
            retired.append(n)
        else:
            node_map[n] = nn
    ref_map = {o: nn for o, nn in node_map.items() if o != nn}

    # 2) new node definitions: NEW_TREE (authoritative) + carried instance leaves --
    new_struct = {addr for addr, _label, _v in NEW_TREE}
    new_nodes: dict[str, tuple[str, str, str | None]] = {
        addr: (label, RF_TXA_ID, view) for addr, label, view in NEW_TREE
    }
    carried: dict[str, str] = {}
    collisions: list[str] = []
    for old, new in node_map.items():
        if new in new_struct:
            continue  # structural — NEW_TREE label/marker/view wins
        if new in new_nodes:
            collisions.append(f"{old}->{new} collides with {carried.get(new, '?')}->{new}")
            continue
        label, marker = old_def[old]
        new_nodes[new] = (label, marker, None)
        carried[new] = old
    if collisions:
        raise SystemExit("NON-INJECTIVE remap (would merge/overwrite leaves):\n  " + "\n  ".join(collisions))

    new_node_set = set(new_nodes)

    # 3) integrity: every parent present + contiguous child ordinals -------------
    closure = _prefix_closure(new_node_set)
    missing_parents = sorted(closure - new_node_set, key=parse_node_addr)
    if missing_parents:
        raise SystemExit(f"new tree missing {len(missing_parents)} parent nodes: {missing_parents[:10]}")
    children: dict[str, list[int]] = {}
    for addr in new_node_set:
        segs = parse_node_addr(addr)
        if len(segs) > 1:
            children.setdefault("-".join(map(str, segs[:-1])), []).append(segs[-1])
    noncontig = {
        parent: sorted(ordn) for parent, ordn in children.items()
        if sorted(ordn) != list(range(1, len(ordn) + 1))
    }
    if noncontig:
        raise SystemExit(f"non-contiguous child ordinals under {len(noncontig)} parents: "
                         f"{dict(list(noncontig.items())[:5])}")

    # 4) rebuild lcl 4-2 block (drop old 4-2-*, write fresh 4-2-1..M in tree order)
    ordered = sorted(new_node_set, key=parse_node_addr)
    new_42: list = []
    expandable: list[tuple[str, str]] = []
    for i, addr in enumerate(ordered, start=1):
        label, marker, view = new_nodes[addr]
        da = f"4-2-{i}"
        head = [da, marker, addr, RF_TITLE, _encode_label_bits(label)]
        if view:
            head += [Markers.VIEW, _encode_label_bits(view)]
            expandable.append((addr, view))
        new_42.append(_row(da, [head, [label]]))
    keep = [r for r in _as_rows(live["lcl"]) if not r.datum_address.startswith("4-2-")]
    new_lcl, lcl_hash = _finalize(dataclasses.replace(live["lcl"], rows=tuple([*keep, *new_42])), "lcl")

    # 5) recompile anchor 1-1-5 lcl-SAMRAS over the new node set -----------------
    lcl_samras_bits = _build_magnitude_bitstream(new_node_set)
    anchor_rows = [
        _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_samras_bits], ["lcl-SAMRAS"]])
        if r.datum_address == ANCHOR_LCL_SAMRAS else r
        for r in _as_rows(live["anchor"])
    ]
    new_anchor, anchor_hash = _finalize(dataclasses.replace(live["anchor"], rows=tuple(anchor_rows)), "anchor")

    docs: dict[str, AuthoritativeDatumDocument] = {"anchor": new_anchor, "lcl": new_lcl}
    hashes: dict[str, str] = {"anchor": anchor_hash, "lcl": lcl_hash}
    prior_ids: dict[str, str] = {"anchor": live["anchor"].document_id, "lcl": live["lcl"].document_id}

    # 6) rewrite consumer docs' lcl refs old→new --------------------------------
    # A node-ref pair (rf.3-1-1 OR rf.3-1-5) is an LCL ref iff its value was a defined lcl
    # node pre-migration (``old_nodes``). This is the only safe discriminator: product_profiles
    # overloads rf.3-1-1 for BOTH genuine txa refs (taxonomy_id) and lcl classification refs,
    # so the marker alone can't tell them apart — but the value's membership in the old lcl
    # tree can (verified: 0 consumer refs hit the 6 addresses shared by both lcl & txa).
    ref_rewrites: dict[str, int] = {}
    dangling: dict[str, list[tuple[str, str]]] = {}
    for name, doc in live.items():
        if name in ("anchor", "lcl", "txa"):
            continue
        overlay: dict[str, object] = {}
        cnt = 0
        dang: list[tuple[str, str]] = []
        for r in _as_rows(doc):
            head = list(r.raw[0])
            modified = False
            for i in range(1, len(head) - 1, 2):
                if not is_node_ref_marker(str(head[i])):
                    continue
                v = str(head[i + 1])
                if v not in old_nodes:
                    continue  # txa ref or literal — leave untouched
                new_v = node_map.get(v)
                if new_v is None:  # referenced an lcl node we RETIRED
                    dang.append((r.datum_address, v))
                    continue
                if new_v != v:
                    head[i + 1] = new_v
                    cnt += 1
                    modified = True
            if modified:
                overlay[r.datum_address] = _row(r.datum_address, [head, *list(r.raw)[1:]])
        ref_rewrites[name] = cnt
        if dang:
            dangling[name] = dang
        if overlay:
            new_doc, h = _rebuild_document(existing=doc, overlay=overlay, name=name)
            docs[name] = new_doc
            hashes[name] = h
            prior_ids[name] = doc.document_id

    report = {
        "old_node_count": len(old_nodes),
        "new_node_count": len(new_node_set),
        "structural_nodes": len(NEW_TREE),
        "carried_leaves": len(carried),
        "retired_nodes": retired,
        "expandable": expandable,
        "ref_rewrites": ref_rewrites,
        "dangling_total": sum(len(v) for v in dangling.values()),
    }
    return Plan(
        docs=docs, hashes=hashes, prior_ids=prior_ids, new_node_set=new_node_set,
        ref_map=ref_map, carried=carried, retired=retired,
        ref_rewrites=ref_rewrites, dangling=dangling, report=report,
    )


# --------------------------------------------------------------------------- #
# Report + verify + run
# --------------------------------------------------------------------------- #
def _print_report(plan: Plan, *, dry_run: bool) -> None:
    r = plan.report
    print("\n============== LCL RESTRUCTURE PLAN ==============")
    print(f"old nodes {r['old_node_count']} → new nodes {r['new_node_count']} "
          f"(structural={r['structural_nodes']}, carried leaves={r['carried_leaves']})")
    print(f"retired nodes : {r['retired_nodes'] or 'none'}")
    print(f"expandable    : {[f'{a}={v}' for a, v in r['expandable']]}")
    print("ref rewrites by doc:")
    for name in sorted(plan.ref_rewrites):
        print(f"  {name:16} {plan.ref_rewrites[name]:4}")
    print("docs touched:")
    for name in plan.docs:
        d = plan.docs[name]
        tag = "(unchanged)" if d.document_id == plan.prior_ids.get(name) else "(CHANGED)"
        print(f"  {name:16} rows={len(d.rows):5}  …{d.document_id.split('.')[-1][:14]}  {tag}")
    if plan.dangling:
        print("DANGLING refs (NOT in new node set) — investigate before --apply:")
        for name, items in plan.dangling.items():
            print(f"  {name}: {items[:8]}{' …' if len(items) > 8 else ''}")
    else:
        print("dangling refs : NONE")
    print("=================================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")


def _verify(authority_db: Path, plan: Plan) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    docs = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    failures: list[str] = []

    lcl = docs.get("lcl")
    defined = _old_definitions(lcl) if lcl else {}
    if set(defined) != plan.new_node_set:
        failures.append(f"lcl defined({len(defined)}) != planned({len(plan.new_node_set)})")

    anchor = docs.get("anchor")
    samras = next((r for r in _as_rows(anchor) if r.datum_address == ANCHOR_LCL_SAMRAS), None) if anchor else None
    denoted = set(decode_canonical_bitstream(str(samras.raw[0][2])).addresses) if samras else set()
    if denoted != _prefix_closure(plan.new_node_set):
        failures.append(f"lcl-SAMRAS denoted({len(denoted)}) != closure({len(_prefix_closure(plan.new_node_set))})")

    # A node ref must resolve to either the new lcl tree OR the txa tree; anything else
    # (and "0"/literals are skipped) is a dangling reference left by the restructure.
    txa_nodes = set(_old_definitions(docs["txa"])) if "txa" in docs else set()
    valid = plan.new_node_set | txa_nodes
    for name, doc in docs.items():
        if name in ("anchor", "lcl", "txa"):
            continue
        for r in _as_rows(doc):
            head = r.raw[0]
            for i in range(1, len(head) - 1, 2):
                if not is_node_ref_marker(str(head[i])):
                    continue
                v = str(head[i + 1])
                if v != "0" and is_node_addr_reference(v) and v not in valid:
                    failures.append(f"{name} {r.datum_address}: dangling node ref {v}")
    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures[:20]))
    print(f"[verify] PASSED — lcl {len(plan.new_node_set)} nodes; denoted==closure; consumer refs resolve")


def run(*, authority_db: Path, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    plan = build(store)
    _print_report(plan, dry_run=dry_run)
    if dry_run:
        return {"status": "dry_run", **plan.report}
    if plan.dangling:
        raise SystemExit(f"refusing to apply: {plan.report['dangling_total']} dangling refs remain "
                         f"(retiring referenced nodes?) — resolve STRUCT_REMAP/NEW_TREE first")

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-lclrestructure-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")

    # anchor + lcl first (the structure), then the repointed consumer docs.
    order = ["anchor", "lcl", *[n for n in plan.docs if n not in ("anchor", "lcl")]]
    for name in order:
        doc = plan.docs[name]
        if doc.document_id == plan.prior_ids.get(name):
            print(f"[skip] {name} unchanged")
            continue
        store.replace_single_document_efficient(
            tenant_id=TENANT, prior_document_id=plan.prior_ids[name], updated_document=doc
        )
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id,
                              version_hash=plan.hashes[name], is_anchor=(name == "anchor"))
        print(f"[write] {name} → …{doc.document_id.split('.')[-1][:14]}")

    _verify(authority_db, plan)
    return {"status": "applied", "backup": str(backup), **plan.report,
            "document_ids": {n: plan.docs[n].document_id for n in plan.docs}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="write (default is a dry-run)")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, dry_run=not args.apply)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
