"""Rectify the agro_erp farm_profile: plots belong to a FIELD inside the largest parcel.

The TASK-006 migration (ingest_agro_erp_farm_plots) packed plots into EACH of the 3 boundary
polygons (5-0-1/2/3), treating every parcel as a "field" — so the map shows equal squares tiling
ALL parcels. The operator's model is: 3 PARCELS, one FIELD that lives inside the largest parcel,
and plots that tile only the FIELD.

This rebuild keeps the 3 parcels (5-0-1/2/3, tail labels parcel_1/2/3) + the property (7-3-1) +
the boundary collection (6-0-1), ADDS a field polygon (5-0-4, tail "field") — a scaled-down copy of
the largest parcel, centered inside it — and re-packs plots into the FIELD only (5-0-5.., tail
plot_N_polygon; rings 4-4-N; features 7-N rf.3-1-5 → re-minted lcl plot nodes). The lcl-SAMRAS
anchor magnitude is recomputed. Backed up + verified; dry-run by default.

NOTE: the field geometry is SYNTHESIZED (a 0.6-scaled copy of the largest parcel) because the
operator's original field was never persisted. Pass --field-scale to tune; supply a real field later.

Usage::

    rectify_farm_field_plots.py --db <copy>                         # DRY-RUN
    rectify_farm_field_plots.py --db <copy> --edge-m 60 --apply      # write
"""
from __future__ import annotations

import argparse
import dataclasses
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shapely.affinity import scale
from shapely.geometry import MultiPolygon, Polygon

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.hops.square_pack import pack_squares, square_to_hops_tokens
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.scripts.cts_gis_geojson_hops_utils import encode_hops_coordinate
from MyCiteV2.scripts.ingest_agro_erp_farm_plots import (
    _BOUNDARY_POLY_MAX,
    _is_plot_row,
    _rebuild_keep_order,
    _ring_coords,
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
    _row,
    _upsert_documents_row,
)

LAND_NODE = "1-2"  # lcl land branch (plots are minted here, reuse-by-title)
_PARCEL_ADDRS = ("5-0-1", "5-0-2", "5-0-3")
_FIELD_POLY = "5-0-4"
_FIELD_RING = "4-5-1"
_PLOTS_COLL = "6-0-2"
_FIELD_COLL = "6-0-3"


def _poly_for(rows_by_addr: dict, poly_addr: str) -> Polygon | None:
    raw = rows_by_addr.get(poly_addr)
    if raw is None:
        return None
    head = raw.raw[0]
    ring_addr = next((str(t).strip() for t in head[1:] if str(t).strip().startswith("4-")), "")
    ring = rows_by_addr.get(ring_addr)
    if ring is None:
        return None
    coords = _ring_coords(ring.raw[0])
    return Polygon(coords) if len(coords) >= 3 else None


def _largest_polygon(poly: Polygon | MultiPolygon) -> Polygon:
    if isinstance(poly, MultiPolygon):
        return max(poly.geoms, key=lambda g: g.area)
    return poly


def _ring_row(ring_addr: str, polygon: Polygon, label: str):
    head = [ring_addr]
    for lon, lat in list(polygon.exterior.coords)[:-1]:  # drop the closing duplicate
        head += [RF_COORD, encode_hops_coordinate(float(lon), float(lat))]
    return _row(ring_addr, [head, [label]])


def build(store: SqliteSystemDatumStoreAdapter, *, edge_m: float, field_scale: float):
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    for name in ("anchor", "lcl", "farm_profile"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found")

    fp_rows = _as_rows(live["farm_profile"])
    boundary = [r for r in fp_rows if not _is_plot_row(r.datum_address)]
    by_addr = {r.datum_address: r for r in boundary}

    # The 3 parcels → polygons; pick the largest; synthesize the FIELD inside it.
    parcels = {a: _poly_for(by_addr, a) for a in _PARCEL_ADDRS}
    if any(p is None for p in parcels.values()):
        raise SystemExit(f"could not decode all parcels: { {a: (p is not None) for a, p in parcels.items()} }")
    largest_addr = max(parcels, key=lambda a: parcels[a].area)
    largest = parcels[largest_addr]
    field = scale(largest, xfact=field_scale, yfact=field_scale, origin="centroid")
    if not largest.contains(field):
        field = _largest_polygon(field.intersection(largest))
    if field.is_empty or field.area <= 0:
        raise SystemExit("synthesized field is empty after clipping to the parcel")

    squares = pack_squares(field, edge_m=edge_m)
    n_plots = len(squares)
    if n_plots == 0:
        raise SystemExit(f"0 plots packed into the field at edge={edge_m} m — choose a smaller --edge-m")

    # lcl: re-mint plot nodes (reuse-by-title under land, like the original ingest).
    lb = LclBuilder(_as_rows(live["lcl"]))
    plot_nodes = [lb.mint_child(LAND_NODE, f"plot_{i}", RF_LCL_ID) for i in range(1, n_plots + 1)]
    new_lcl, lcl_hash = _rebuild_keep_order(existing=live["lcl"], overlay=lb.overlay, name="lcl")

    # anchor: recompute the lcl-SAMRAS magnitude over the (possibly grown) node set.
    lcl_bits = _build_magnitude_bitstream(lb.node_set)
    anchor_rows = [
        _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_bits], ["lcl-SAMRAS"]])
        if r.datum_address == ANCHOR_LCL_SAMRAS else r
        for r in _as_rows(live["anchor"])
    ]
    new_anchor, anchor_hash = _finalize(dataclasses.replace(live["anchor"], rows=tuple(anchor_rows)), "anchor")

    # farm_profile: keep property + parcels + boundary collection; add the field; re-pack plots into it.
    keep = [r for r in boundary if r.datum_address not in (_FIELD_POLY, _FIELD_RING, _FIELD_COLL)]
    new_rows = list(keep)
    # FIELD polygon (tail label "field" — the tool classifies by this label)
    new_rows.append(_ring_row(_FIELD_RING, field, "field_ring"))
    new_rows.append(_row(_FIELD_POLY, [[_FIELD_POLY, "~", _FIELD_RING], ["field"]]))
    new_rows.append(_row(_FIELD_COLL, [[_FIELD_COLL, "~", _FIELD_POLY], ["field_collection"]]))
    # PLOTS tiling the field (polys 5-0-5.., rings 4-4-i, features 7-(4+i)-1)
    plot_polys: list[str] = []
    for i, (square, node) in enumerate(zip(squares, plot_nodes, strict=True), start=1):
        ring_addr = f"4-4-{i}"
        ring_head = [ring_addr]
        for token in square_to_hops_tokens(square):
            ring_head += [RF_COORD, token]
        new_rows.append(_row(ring_addr, [ring_head, [f"plot_{i}_ring"]]))
        poly_addr = f"5-0-{_BOUNDARY_POLY_MAX + 1 + i}"  # field is 5-0-4, plots start 5-0-5
        plot_polys.append(poly_addr)
        new_rows.append(_row(poly_addr, [[poly_addr, "~", ring_addr], [f"plot_{i}_polygon"]]))
        feat_addr = f"7-{_BOUNDARY_POLY_MAX + 1 + i}-1"
        label = f"plot_{i}"
        new_rows.append(_row(
            feat_addr,
            [[feat_addr, RF_LCL_ID, node, RF_TITLE, _encode_label_bits(label), poly_addr, "1"], [label]],
        ))
    new_rows.append(_row(_PLOTS_COLL, [[_PLOTS_COLL, "~", *plot_polys], ["plots_collection"]]))

    new_fp, fp_hash = _finalize(dataclasses.replace(live["farm_profile"], rows=tuple(new_rows)), "farm_profile")
    report = {
        "largest_parcel": largest_addr,
        "field_scale": field_scale,
        "edge_m": edge_m,
        "plots_in_field": n_plots,
        "farm_profile_rows": len(new_rows),
        "lcl_node_count": len(lb.node_set),
    }
    docs = {"anchor": new_anchor, "lcl": new_lcl, "farm_profile": new_fp}
    hashes = {"anchor": anchor_hash, "lcl": lcl_hash, "farm_profile": fp_hash}
    prior = {n: live[n].document_id for n in docs}
    return docs, prior, hashes, report


def run(*, authority_db: Path, edge_m: float, field_scale: float, dry_run: bool) -> dict:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    docs, prior, hashes, report = build(store, edge_m=edge_m, field_scale=field_scale)
    print("== rectify farm field/plots ==")
    for k, v in report.items():
        print(f"  {k}: {v}")
    for name, doc in docs.items():
        tag = "(unchanged)" if doc.document_id == prior[name] else "(CHANGED)"
        print(f"  {name:13} rows={len(doc.rows):4} {tag}")
    if dry_run:
        print("DRY RUN — nothing written.")
        return report
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-fieldplots-{stamp}.bak")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    for name, doc in docs.items():
        if doc.document_id == prior[name]:
            continue
        store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=prior[name], updated_document=doc)
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id,
                              version_hash=hashes[name], is_anchor=(name == "anchor"))
    print("[applied]")
    return report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Put farm plots inside a field within the largest parcel.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--edge-m", type=float, default=60.0)
    ap.add_argument("--field-scale", type=float, default=0.6)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    run(authority_db=Path(args.db), edge_m=args.edge_m, field_scale=args.field_scale, dry_run=not args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
