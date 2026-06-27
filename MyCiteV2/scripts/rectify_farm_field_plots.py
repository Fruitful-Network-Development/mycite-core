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

NOTE: the field geometry is the operator's REAL polygon (_REAL_FIELD_COORDS — a 24-point ring inside
parcel_1, the largest parcel). Pass --field-json <path> to override it, or --synthesize to fall back to
the old 0.6-scaled copy of the largest parcel.

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

# The operator's REAL field polygon (lon, lat), a 24-point ring that sits inside parcel_1 (5-0-1),
# the largest parcel — verified read-only (containment 1.000). This replaces the synthesized 0.6-scale
# copy. Override with --field-json <path> ([[lon,lat],...]); --synthesize falls back to the scaled copy.
_REAL_FIELD_COORDS: tuple[tuple[float, float], ...] = (
    (-81.52656332227225, 41.23557837471115),
    (-81.52590977635926, 41.23538503761906),
    (-81.52581068075156, 41.23541790753577),
    (-81.52568382163648, 41.23536763009513),
    (-81.52445291028205, 41.23494564790477),
    (-81.52435875940715, 41.23496977947267),
    (-81.52416198646841, 41.23483960368717),
    (-81.52374782851138, 41.23471175283589),
    (-81.52364212171024, 41.23486920210374),
    (-81.5235388062879, 41.23521391931826),
    (-81.52350412006453, 41.23565298737125),
    (-81.52367045468824, 41.23568573746464),
    (-81.52378841332548, 41.23584933682286),
    (-81.52427451689701, 41.23609651736726),
    (-81.52492853259835, 41.23617053497404),
    (-81.52535558116618, 41.23614368836691),
    (-81.52572350120239, 41.23621821306675),
    (-81.52576744040692, 41.23628399987388),
    (-81.5263846849648, 41.23652423963335),
    (-81.52674785876901, 41.23646518353768),
    (-81.52682381395185, 41.23648028857871),
    (-81.5272671789082, 41.23642694774269),
    (-81.52732277939828, 41.23561665240299),
    (-81.52656332227225, 41.23557837471115),
)


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


def build(
    store: SqliteSystemDatumStoreAdapter,
    *,
    edge_m: float,
    field_coords: tuple[tuple[float, float], ...] | None = None,
    field_scale: float = 0.6,
    synthesize: bool = False,
):
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    for name in ("anchor", "lcl", "farm_profile"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found")

    fp_rows = _as_rows(live["farm_profile"])
    boundary = [r for r in fp_rows if not _is_plot_row(r.datum_address)]
    by_addr = {r.datum_address: r for r in boundary}

    # The 3 parcels → polygons; pick the largest. The FIELD is the operator's real polygon (default),
    # validated to sit inside the largest parcel; --synthesize falls back to a scaled copy of it.
    parcels = {a: _poly_for(by_addr, a) for a in _PARCEL_ADDRS}
    if any(p is None for p in parcels.values()):
        raise SystemExit(f"could not decode all parcels: { {a: (p is not None) for a, p in parcels.items()} }")
    largest_addr = max(parcels, key=lambda a: parcels[a].area)
    largest = parcels[largest_addr]
    if synthesize or field_coords is None:
        field = scale(largest, xfact=field_scale, yfact=field_scale, origin="centroid")
        if not largest.contains(field):
            field = _largest_polygon(field.intersection(largest))
        if field.is_empty or field.area <= 0:
            raise SystemExit("synthesized field is empty after clipping to the parcel")
        field_origin = f"synthesized(scale={field_scale})"
    else:
        field = Polygon([(float(lon), float(lat)) for lon, lat in field_coords])
        if not field.is_valid or field.area <= 0:
            raise SystemExit("provided field polygon is invalid or zero-area")
        if not largest.contains(field):
            # The operator's field is authoritative — warn, do NOT clip it to the parcel.
            ratio = field.intersection(largest).area / field.area if field.area else 0.0
            print(f"[warn] provided field is NOT fully contained by the largest parcel {largest_addr} "
                  f"(field∩largest/field={ratio:.3f}); keeping the operator geometry as-is")
        field_origin = "operator_provided"

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
        "field_origin": field_origin,
        "field_in_largest": largest.contains(field),
        "edge_m": edge_m,
        "plots_in_field": n_plots,
        "farm_profile_rows": len(new_rows),
        "lcl_node_count": len(lb.node_set),
    }
    docs = {"anchor": new_anchor, "lcl": new_lcl, "farm_profile": new_fp}
    hashes = {"anchor": anchor_hash, "lcl": lcl_hash, "farm_profile": fp_hash}
    prior = {n: live[n].document_id for n in docs}
    return docs, prior, hashes, report


def run(
    *,
    authority_db: Path,
    edge_m: float,
    field_coords: tuple[tuple[float, float], ...] | None,
    field_scale: float,
    synthesize: bool,
    dry_run: bool,
) -> dict:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    docs, prior, hashes, report = build(
        store, edge_m=edge_m, field_coords=field_coords, field_scale=field_scale, synthesize=synthesize
    )
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


def _load_field_json(path: str) -> tuple[tuple[float, float], ...]:
    import json

    data = json.loads(Path(path).read_text())
    return tuple((float(lon), float(lat)) for lon, lat in data)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Put farm plots inside a field within the largest parcel.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--edge-m", type=float, default=30.0, help="plot square edge in metres (default 30 ≈ fine tiling)")
    ap.add_argument("--field-json", help="override the embedded real field with a [[lon,lat],...] JSON file")
    ap.add_argument("--field-scale", type=float, default=0.6, help="only with --synthesize: scale of the parcel copy")
    ap.add_argument("--synthesize", action="store_true", help="fall back to a scaled copy of the largest parcel")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    field_coords = (
        None if args.synthesize
        else _load_field_json(args.field_json) if args.field_json
        else _REAL_FIELD_COORDS
    )
    run(
        authority_db=Path(args.db),
        edge_m=args.edge_m,
        field_coords=field_coords,
        field_scale=args.field_scale,
        synthesize=args.synthesize,
        dry_run=not args.apply,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
