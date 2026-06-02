"""Migrate field plots INTO the agro_erp farm_profile and retire the plots doc.

Implements plans/TASK-003-farm-plot-model.md (TASK-2026-06-02-006): square-pack each
farm_profile field polygon into equal real-world squares fully inside it, mint one LCL
local_id per plot, and write each plot as a CTS-GIS HOPS feature (ring 4-4-i → poly
5-0-(3+i) → feature 7-(3+i)-1, rf.3-1-5 lcl-id) inside farm_profile, gathered by a vg0
collection (6-0-2). The standalone ``plots`` document is then retired.

Idempotent: the farm_profile is reconstructed deterministically from its BOUNDARY rows
plus freshly-packed plot rows, so re-running (same --plot-edge-m) reproduces byte-identical
ids. LCL plot nodes reuse-by-title. Mirrors the ingest discipline of
ingest_agro_erp_ledger (copy → dry-run → verify → apply live with backup).

Usage:
    python -m MyCiteV2.scripts.ingest_agro_erp_farm_plots --authority-db DB [--plot-edge-m 30] --dry-run
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import sqlite3
import time
from pathlib import Path

from shapely.geometry import Polygon

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.hops.square_pack import pack_squares, square_to_hops_tokens
from MyCiteV2.packages.core.structures.hops import decode_hops_coordinate_token
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    ANCHOR_LCL_SAMRAS,
    RF_COORD,
    RF_LCL_ID,
    RF_TITLE,
    SANDBOX,
    TENANT,
    LclBuilder,
    _as_rows,
    _build_magnitude_bitstream,
    _encode_label_bits,
    _finalize,
    _prefix_closure,
    _row,
    _upsert_documents_row,
)

# Default plot edge (metres) — a fixed real-world plot size (~1 ha at 100 m), giving a
# manageable plot count on the live field. Override with --plot-edge-m; smaller values
# pack many more, finer plots (e.g. 30 m → ~420). Idempotent re-run applies a new size.
DEFAULT_PLOT_EDGE_M = 100.0
LAND_NODE = "1-2"  # lcl "land" branch; plots are direct children (siblings of "property")

# farm_profile plot-row address families (must not collide with the boundary).
_PLOT_RING_RE = re.compile(r"^4-4-\d+$")
_PLOT_POLY_RE = re.compile(r"^5-0-(\d+)$")   # boundary polys are 5-0-1..3; plots 5-0-4+
_PLOT_FEAT_RE = re.compile(r"^7-(\d+)-1$")   # boundary feature is 7-3-1; plots 7-4-1+
_PLOT_COLL = "6-0-2"
_BOUNDARY_POLY_MAX = 3  # 5-0-1/2/3 are the property fields


def _is_plot_row(addr: str) -> bool:
    if _PLOT_RING_RE.match(addr) or addr == _PLOT_COLL:
        return True
    m = _PLOT_POLY_RE.match(addr)
    if m and int(m.group(1)) > _BOUNDARY_POLY_MAX:
        return True
    m = _PLOT_FEAT_RE.match(addr)
    if m and int(m.group(1)) > _BOUNDARY_POLY_MAX:
        return True
    return False


def _ring_coords(head: list) -> list[tuple[float, float]]:
    coords: list[tuple[float, float]] = []
    for i in range(len(head) - 1):
        if str(head[i]).strip() == RF_COORD:
            decoded = decode_hops_coordinate_token(str(head[i + 1]).strip())
            if decoded:
                coords.append((decoded["longitude"]["value"], decoded["latitude"]["value"]))
    return coords


def _field_polygons(boundary_rows: list[AuthoritativeDatumDocumentRow]) -> list[Polygon]:
    """The property field polygons (boundary 5-0-1..3 → their family-4 rings)."""
    by_addr = {r.datum_address: r for r in boundary_rows}
    fields: list[Polygon] = []
    for addr, row in sorted(by_addr.items()):
        m = _PLOT_POLY_RE.match(addr)
        if not (m and int(m.group(1)) <= _BOUNDARY_POLY_MAX):
            continue
        head = row.raw[0]
        ring_addr = next((str(t).strip() for t in head[1:] if str(t).strip().startswith("4-")), "")
        ring = by_addr.get(ring_addr)
        if ring is None:
            continue
        coords = _ring_coords(ring.raw[0])
        if len(coords) >= 3:
            fields.append(Polygon(coords))
    return fields


@dataclasses.dataclass
class Plan:
    docs: dict[str, AuthoritativeDatumDocument]
    hashes: dict[str, str]
    prior_ids: dict[str, str | None]
    plots_prior_id: str | None
    report: dict
    expect: dict


def build(store: SqliteSystemDatumStoreAdapter, *, edge_m: float) -> Plan:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
    for name in ("anchor", "lcl", "farm_profile"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found in catalog")

    fp_rows = _as_rows(live["farm_profile"])
    boundary = [r for r in fp_rows if not _is_plot_row(r.datum_address)]
    if any(_PLOT_RING_RE.match(r.datum_address) for r in boundary):
        raise SystemExit("a boundary ring already uses the 4-4-* plot family; aborting to avoid collision")

    fields = _field_polygons(boundary)
    if not fields:
        raise SystemExit("no field polygons decoded from farm_profile boundary")

    squares: list[Polygon] = []
    per_field: list[int] = []
    for poly in fields:
        packed = pack_squares(poly, edge_m=edge_m)
        per_field.append(len(packed))
        squares.extend(packed)
    n_plots = len(squares)
    if n_plots == 0:
        raise SystemExit(f"0 plots packed at edge={edge_m} m — choose a smaller --plot-edge-m")

    # --- LCL: mint one plot node per square (reuse-by-title) ------------------
    lb = LclBuilder(_as_rows(live["lcl"]))
    plot_nodes: list[str] = [lb.mint_child(LAND_NODE, f"plot_{i}", RF_LCL_ID) for i in range(1, n_plots + 1)]
    new_lcl, lcl_hash = _rebuild_keep_order(existing=live["lcl"], overlay=lb.overlay, name="lcl")

    # --- anchor: recompute lcl-SAMRAS magnitude; drop the retired plots pointer
    lcl_samras_bits = _build_magnitude_bitstream(lb.node_set)
    anchor_rows = [r for r in _as_rows(live["anchor"])
                   if not (r.datum_address.startswith("1-0-")
                           and "plots" in str((r.raw[1] or [""])[0] if len(r.raw) > 1 else ""))]
    anchor_rows = [
        _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_samras_bits], ["lcl-SAMRAS"]])
        if r.datum_address == ANCHOR_LCL_SAMRAS else r
        for r in anchor_rows
    ]
    new_anchor, anchor_hash = _finalize(dataclasses.replace(live["anchor"], rows=tuple(anchor_rows)), "anchor")

    # --- farm_profile: boundary rows + fresh plot rows + collection ----------
    plot_rows: list[AuthoritativeDatumDocumentRow] = []
    for i, (square, node) in enumerate(zip(squares, plot_nodes, strict=True), start=1):
        ring_addr = f"4-4-{i}"
        ring_head = [ring_addr]
        for token in square_to_hops_tokens(square):
            ring_head += [RF_COORD, token]
        plot_rows.append(_row(ring_addr, [ring_head, [f"plot_{i}_ring"]]))
        poly_addr = f"5-0-{_BOUNDARY_POLY_MAX + i}"
        plot_rows.append(_row(poly_addr, [[poly_addr, "~", ring_addr], [f"plot_{i}_polygon"]]))
        feat_addr = f"7-{_BOUNDARY_POLY_MAX + i}-1"
        label = f"plot_{i}"
        plot_rows.append(_row(
            feat_addr,
            [[feat_addr, RF_LCL_ID, node, RF_TITLE, _encode_label_bits(label), poly_addr, "1"], [label]],
        ))
    coll_head = [_PLOT_COLL, "~"] + [f"5-0-{_BOUNDARY_POLY_MAX + i}" for i in range(1, n_plots + 1)]
    plot_rows.append(_row(_PLOT_COLL, [coll_head, ["plots_collection"]]))

    new_fp_rows = list(boundary) + plot_rows
    new_fp, fp_hash = _finalize(dataclasses.replace(live["farm_profile"], rows=tuple(new_fp_rows)), "farm_profile")

    plots_doc = live.get("plots")
    report = {
        "edge_m": edge_m,
        "fields": len(fields),
        "plots_per_field": per_field,
        "plots_total": n_plots,
        "lcl_rows_added": len(lb.overlay),
        "lcl_node_count": len(lb.node_set),
        "lcl_closure": len(_prefix_closure(lb.node_set)),
        "farm_profile_rows": len(new_fp_rows),
        "plots_doc_retired": bool(plots_doc),
    }
    expect = {
        "farm_profile_rows": len(new_fp_rows),
        "lcl_closure": len(_prefix_closure(lb.node_set)),
        "plots_absent": True,
        "plot_features": n_plots,
    }
    return Plan(
        docs={"anchor": new_anchor, "lcl": new_lcl, "farm_profile": new_fp},
        hashes={"anchor": anchor_hash, "lcl": lcl_hash, "farm_profile": fp_hash},
        prior_ids={
            "anchor": live["anchor"].document_id,
            "lcl": live["lcl"].document_id,
            "farm_profile": live["farm_profile"].document_id,
        },
        plots_prior_id=(plots_doc.document_id if plots_doc else None),
        report=report,
        expect=expect,
    )


def _rebuild_keep_order(*, existing, overlay, name):
    out: list[AuthoritativeDatumDocumentRow] = []
    seen: set[str] = set()
    for r in _as_rows(existing):
        if r.datum_address in overlay:
            out.append(overlay[r.datum_address])
            seen.add(r.datum_address)
        else:
            out.append(r)
    for a, r in overlay.items():
        if a not in seen:
            out.append(r)
    return _finalize(dataclasses.replace(existing, rows=tuple(out)), name)


def _print_report(plan: Plan, *, dry_run: bool) -> None:
    r = plan.report
    print("\n============ FARM-PLOT MIGRATION PLAN ============")
    print(f"plot edge (m)        : {r['edge_m']}")
    print(f"fields               : {r['fields']}  plots/field={r['plots_per_field']}")
    print(f"PLOTS (total)        : {r['plots_total']}")
    print(f"lcl rows added       : {r['lcl_rows_added']}  (node_count={r['lcl_node_count']}, closure={r['lcl_closure']})")
    print(f"farm_profile rows    : {r['farm_profile_rows']}")
    print(f"plots doc retired    : {r['plots_doc_retired']}")
    for name in ("anchor", "lcl", "farm_profile"):
        d = plan.docs[name]
        prior = plan.prior_ids[name]
        tag = "(unchanged)" if d.document_id == prior else "(CHANGED)"
        print(f"  {name:13} rows={len(d.rows):5}  …{d.document_id.split('.')[-1][:14]}  {tag}")
    print("==================================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")


def _verify(authority_db: Path, *, expect: dict) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    docs = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    failures: list[str] = []
    if "plots" in docs and expect["plots_absent"]:
        failures.append("plots document still present after retirement")
    fp = docs.get("farm_profile")
    if fp is None:
        failures.append("farm_profile missing")
    else:
        if len(fp.rows) != expect["farm_profile_rows"]:
            failures.append(f"farm_profile rows={len(fp.rows)} expected {expect['farm_profile_rows']}")
        feats = [r for r in _as_rows(fp) if _PLOT_FEAT_RE.match(r.datum_address) and int(_PLOT_FEAT_RE.match(r.datum_address).group(1)) > _BOUNDARY_POLY_MAX]
        if len(feats) != expect["plot_features"]:
            failures.append(f"plot features={len(feats)} expected {expect['plot_features']}")
        # every plot feature references an existing lcl node + an existing poly (no dangling)
        addrs = {r.datum_address for r in _as_rows(fp)}
        lcl_nodes = set()
        for r in _as_rows(docs["lcl"]):
            if r.datum_address.startswith("4-2-") and len(r.raw[0]) >= 3:
                lcl_nodes.add(str(r.raw[0][2]))
        for r in feats:
            head = r.raw[0]
            node = str(head[2])
            poly = str(head[5]) if len(head) > 5 else ""
            if node not in lcl_nodes:
                failures.append(f"{r.datum_address} dangling lcl node {node}")
            if poly not in addrs:
                failures.append(f"{r.datum_address} dangling poly {poly}")
    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures))
    print("[verify] post-write checks PASSED")


def run(*, authority_db: Path, edge_m: float, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    plan = build(store, edge_m=edge_m)
    _print_report(plan, dry_run=dry_run)
    if dry_run:
        return {"status": "dry_run", **plan.report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-farmplots-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")

    for name in ("anchor", "lcl", "farm_profile"):
        doc = plan.docs[name]
        if doc.document_id == plan.prior_ids[name]:
            print(f"[skip] {name} already current")
            continue
        store.replace_single_document_efficient(
            tenant_id=TENANT, prior_document_id=plan.prior_ids[name], updated_document=doc
        )
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id,
                              version_hash=plan.hashes[name], is_anchor=(name == "anchor"))
        print(f"[write] {name} → …{doc.document_id.split('.')[-1][:14]}")

    if plan.plots_prior_id:
        store.delete_authoritative_document(tenant_id=TENANT, document_id=plan.plots_prior_id)
        conn = sqlite3.connect(authority_db)
        try:
            conn.execute("DELETE FROM documents WHERE tenant_id=? AND sandbox=? AND name=?", (TENANT, SANDBOX, "plots"))
            conn.commit()
        finally:
            conn.close()
        print("[retire] plots document removed")

    _verify(authority_db, expect=plan.expect)
    return {"status": "applied", "backup": str(backup), **plan.report,
            "document_ids": {n: plan.docs[n].document_id for n in ("anchor", "lcl", "farm_profile")}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--plot-edge-m", type=float, default=DEFAULT_PLOT_EDGE_M, help="fixed real-world plot edge length in metres")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    result = run(authority_db=args.authority_db, edge_m=args.plot_edge_m, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
