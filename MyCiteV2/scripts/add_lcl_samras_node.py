#!/usr/bin/env python3
"""Add a SAMRAS **lcl** node CONSISTENTLY.

The dendrogram builds the node tree from the authoritative magnitude bitstream (anchor row
``1-1-5``, decoded via ``decode_canonical_bitstream``) and overlays ASCII labels from the lcl
definition rows. So adding a node requires BOTH:

  1. recompiling the lcl magnitude bitstream to include the new node (``recompiled_magnitude_raw``
     → ``build_magnitude_bitstream``, which round-trip-asserts so a corrupt encoding can never be
     written), and
  2. inserting the node-definition row ``[[4-2-N, rf.3-1-1, <node>, rf.3-1-2, <title bits>], [<title>]]``
     so the node renders with its title.

A bare ``insert_datum`` (the generic editing UI) does step 2 only — the node would stay invisible in
the dendrogram. This DESTRUCTIVE script does both via the tested mutation pipeline.

Usage::

    add_lcl_samras_node.py --db <path> --node 1-8 --title event_type            # DRY-RUN (no write)
    add_lcl_samras_node.py --db <path> --node 1-8 --title event_type --apply     # write

Back up the authority DB first. Defaults to the live DB path; pass --db to target a copy.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_datum_workbench_mutation_runtime import (
    run_datum_workbench_mutation_action,
)
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.labels import encode_label_bits
from MyCiteV2.packages.core.datum_ops.samras_deps import recompiled_magnitude_raw
from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest

LIVE_DB = "/srv/webapps/mycite/fnd/private/mos_authority.sqlite3"
LCL_MAG_ADDR = "1-1-5"  # the lcl-SAMRAS magnitude row in the anchor


def _head(row):
    raw = row.raw
    return raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else []


def add_lcl_node(db: str, node: str, title: str, *, apply: bool) -> bool:
    store = SqliteSystemDatumStoreAdapter(db, allow_legacy_writes=False)
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id="fnd"))
    anchor = next(d for d in cat.documents if ".agro_erp.anchor." in d.document_id)
    lcl = next(d for d in cat.documents if ".agro_erp.lcl." in d.document_id)
    mag_row = next(r for r in anchor.rows if r.datum_address == LCL_MAG_ADDR)

    addrs = set(decode_canonical_bitstream(_head(mag_row)[2]).addresses)
    if node in addrs:
        print(f"node {node!r} already present ({len(addrs)} nodes) — nothing to do")
        return False
    new_addrs = set(addrs)
    new_addrs.add(node)
    new_mag_raw = recompiled_magnitude_raw(mag_row, new_addrs)  # roundtrip-asserted inside

    maxdef = max(
        (int(r.datum_address.split("-")[2]) for r in lcl.rows if r.datum_address.startswith("4-2-")),
        default=0,
    )
    def_addr = f"4-2-{maxdef + 1}"
    def_raw = [[def_addr, "rf.3-1-1", node, "rf.3-1-2", encode_label_bits(title)], [title]]

    print(f"node {node!r} (title {title!r}): {len(addrs)} -> {len(new_addrs)} nodes")
    print(f"  anchor {anchor.document_id} row {LCL_MAG_ADDR}: recompiled magnitude bitstream")
    print(f"  lcl {lcl.document_id} insert {def_addr}: definition row")
    if not apply:
        print("DRY-RUN — no write")
        return True

    r1 = run_datum_workbench_mutation_action(
        "apply",
        {
            "target_authority": "datum_workbench",
            "sandbox_id": "agro_erp",
            "document_id": anchor.document_id,
            "datum_address": LCL_MAG_ADDR,
            "operation": "update_row_raw",
            "payload_text": json.dumps(new_mag_raw),
        },
        authority_db_file=db,
        portal_instance_id="fnd",
    )
    if not r1.get("ok"):
        raise SystemExit(f"magnitude update failed: {r1}")
    r2 = run_datum_workbench_mutation_action(
        "apply",
        {
            "target_authority": "datum_workbench",
            "sandbox_id": "agro_erp",
            "document_id": lcl.document_id,
            "datum_address": def_addr,
            "operation": "insert_datum",
            "payload_text": json.dumps(def_raw),
        },
        authority_db_file=db,
        portal_instance_id="fnd",
    )
    if not r2.get("ok"):
        raise SystemExit(f"definition insert failed (magnitude already updated!): {r2}")
    print("APPLIED")
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Add a SAMRAS lcl node (bitstream + definition row).")
    ap.add_argument("--db", default=LIVE_DB)
    ap.add_argument("--node", required=True, help="node address, e.g. 1-8")
    ap.add_argument("--title", required=True, help="ASCII title, e.g. event_type")
    ap.add_argument("--apply", action="store_true", help="write (default is a dry-run)")
    args = ap.parse_args(argv)
    add_lcl_node(args.db, args.node, args.title, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
