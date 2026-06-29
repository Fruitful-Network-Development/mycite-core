"""Agro_erp domain write actions (POST /portal/api/v2/agro/<action>).

The generic mutation route takes a fully-formed raw row; these two actions do the encode-heavy
domain transactions the client cannot (HOPS dates, nominal bits, lcl node minting + magnitude
recompile, union geometry):

* ``save_contract`` — build a contract row (date HOPS-encoded, referent = cluster OR plot, event
  = investment) and append/dedup it (reuses the proven ``add_agro_erp_contract`` builder).
* ``create_cluster`` — dissolve-union the selected plots' polygons into an outline, mint a
  ``cluster_N`` lcl node under a new land ``cluster`` (1-2-5), recompile the anchor magnitude, and
  record the cluster geometry + a reference to the selected plot collection under farm_profile.

Both back up + persist via the canonical store. Auth is the proxy's (same as the mutation route).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.datum_resolve import resolve_coordinate
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.scripts.cts_gis_geojson_hops_utils import encode_hops_coordinate
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    ANCHOR_LCL_SAMRAS,
    ANCHOR_TIME_PRIMITIVE,
    RF_COORD,
    RF_LCL_ID,
    RF_TITLE,
    RF_TXA_ID,
    RF_UTC,
    SANDBOX,
    TENANT,
    LclBuilder,
    _as_rows,
    _build_magnitude_bitstream,
    _encode_label_bits,
    _finalize,
    _row,
    _upsert_documents_row,
    build_chronology_authority,
    encode_utc_datetime_as_hops,
    schema_from_anchor_payload,
)

LAND_CLUSTER = "1-2"  # cluster container is minted as the next land child (→ 1-2-5)


def _err(msg: str) -> dict[str, Any]:
    return {"ok": False, "error": msg}


def _hops_day(cts_anchor: Any, day: str) -> str:
    """Encode an ISO (YYYY-MM-DD) or MM-DD-YYYY day → a HOPS-UTC token via the cts_gis clock."""
    rows = {r.datum_address: r.raw for r in _as_rows(cts_anchor)}
    t = rows.get("1-1-5")
    schema = schema_from_anchor_payload({"1-1-1": [["1-1-1", ANCHOR_TIME_PRIMITIVE, str(t[0][2])], ["HOPS-chronological"]]})
    chrono = build_chronology_authority(
        schema_payload=schema, quadrennium_payload={"3-1-1": [["3-1-1", "~", "0"], ["quadrennium"]]},
        cosmological_prefix=(0, 0),
    )
    s = day.strip()
    if "-" in s and len(s.split("-")[0]) == 4:           # YYYY-MM-DD
        y, m, d = (int(x) for x in s.split("-")[:3])
    else:                                                # MM-DD-YYYY
        m, d, y = (int(x) for x in s.split("-")[:3])
    return encode_utc_datetime_as_hops(datetime(y, m, d, tzinfo=UTC), authority=chrono)


# --------------------------------------------------------------------------- #
def save_contract(authority_db: Path, *, sandbox_id: str, date: str, invoice_node: str,
                  referent_node: str, amount: str, cost: str, datum_address: str = "") -> dict[str, Any]:
    """Create (append/dedup) a contract referencing a cluster OR plot. Reuses the contract builder."""
    from MyCiteV2.scripts import add_agro_erp_contract as C
    if not (date and invoice_node and referent_node and amount and cost):
        return _err("date, invoice, referent, amount and cost are all required")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    try:
        plan = C.build(store, invoice=invoice_node, plot=referent_node, amount=amount, cost=cost, date=date)
    except SystemExit as exc:  # draw-down exceeded / unit mismatch / unresolved node
        return _err(str(exc))
    if plan.doc.document_id == plan.prior_id:
        return {"ok": True, "noop": True, "datum_address": plan.report.get("contract_addr", "")}
    store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=plan.prior_id, updated_document=plan.doc)
    _upsert_documents_row(authority_db, name="contracts", document_id=plan.doc.document_id,
                          version_hash=plan.version_hash, is_anchor=False)
    return {"ok": True, "datum_address": plan.report["contract_addr"], **plan.report}


# --------------------------------------------------------------------------- #
def create_cluster(authority_db: Path, *, sandbox_id: str, plot_nodes: list[str], day: str) -> dict[str, Any]:
    """Dissolve-union the selected plots → an outline cluster, minted + recorded under farm_profile."""
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.ops import unary_union
    if not plot_nodes:
        return _err("no plots selected")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, Any] = {}
    cts_anchor = None
    for d in cat.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
        elif ".cts_gis.anchor." in d.document_id:
            cts_anchor = d
    for n in ("anchor", "lcl", "farm_profile"):
        if n not in live:
            return _err(f"agro_erp.{n} not found")
    if cts_anchor is None:
        return _err("cts_gis anchor (clock) not found")

    fp_rows = {r.datum_address: r for r in _as_rows(live["farm_profile"])}
    # plot lcl node -> its polygon ring coords (via the 7-* feature → 5-0-* polygon → 4-* ring).
    node_poly: dict[str, str] = {}
    selected_polys: list[Polygon] = []
    selected_poly_addrs: list[str] = []
    for addr, row in fp_rows.items():
        if not addr.startswith("7-"):
            continue
        head = row.raw[0]
        node = next((str(head[i + 1]) for i in range(1, len(head) - 1, 2) if str(head[i]).lower() == RF_LCL_ID), "")
        poly_addr = next((str(t) for t in head[2:] if str(t).startswith("5-")), "")
        if node:
            node_poly[node] = poly_addr
    for pn in plot_nodes:
        paddr = node_poly.get(pn)
        prow = fp_rows.get(paddr) if paddr else None
        if prow is None:
            continue
        ring_addr = next((str(t) for t in prow.raw[0][1:] if str(t).startswith("4-")), "")
        ring = fp_rows.get(ring_addr)
        if ring is None:
            continue
        coords = resolve_coordinate(ring.raw[0])
        if len(coords) >= 3:
            selected_polys.append(Polygon(coords))
            selected_poly_addrs.append(paddr)
    if not selected_polys:
        return _err("none of the selected plots have resolvable geometry")

    union = unary_union(selected_polys)
    outline_polys = list(union.geoms) if isinstance(union, MultiPolygon) else [union]

    # --- lcl: ensure the cluster container + mint cluster_N; recompile the magnitude ----------
    lb = LclBuilder(_as_rows(live["lcl"]))
    container = lb.mint_child(LAND_CLUSTER, "cluster", RF_TXA_ID)  # → 1-2-5 (reuse-by-title)
    existing_clusters = sum(1 for n in lb.node_set if n.startswith(container + "-"))
    cluster_name = f"cluster_{existing_clusters + 1}"
    cluster_node = lb.mint_child(container, cluster_name, RF_LCL_ID)
    from MyCiteV2.scripts.ingest_agro_erp_ledger import _rebuild_document
    new_lcl, lcl_hash = _rebuild_document(existing=live["lcl"], overlay=lb.overlay, name="lcl")
    lcl_bits = _build_magnitude_bitstream(lb.node_set)
    anchor_rows = [
        _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_bits], ["lcl-SAMRAS"]])
        if r.datum_address == ANCHOR_LCL_SAMRAS else r for r in _as_rows(live["anchor"])
    ]
    new_anchor, anchor_hash = _finalize(dataclasses.replace(live["anchor"], rows=tuple(anchor_rows)), "anchor")

    # --- farm_profile: cluster ring(s) (4-6-*) + polygon(s) (5-0-*) + collection (6-0-*) of the
    #     selected plot polys (the plot-collection denotation) + the cluster feature (7-*-1) -----
    def _max_n(prefix: str, seg: int) -> int:
        return max((int(r.datum_address.split("-")[seg]) for r in _as_rows(live["farm_profile"])
                    if r.datum_address.startswith(prefix)), default=0)
    ring_base = _max_n("4-6-", 2)
    poly_base = max((int(r.datum_address.split("-")[2]) for r in _as_rows(live["farm_profile"])
                     if r.datum_address.startswith("5-0-")), default=0)
    coll_base = _max_n("6-0-", 2)
    feat_base = max((int(r.datum_address.split("-")[1]) for r in _as_rows(live["farm_profile"])
                     if r.datum_address.startswith("7-")), default=0)

    new_rows = list(_as_rows(live["farm_profile"]))
    cluster_poly_addrs: list[str] = []
    for i, poly in enumerate(outline_polys, start=1):
        ring_addr = f"4-6-{ring_base + i}"
        ring_head = [ring_addr]
        for lon, lat in list(poly.exterior.coords)[:-1]:
            ring_head += [RF_COORD, encode_hops_coordinate(float(lon), float(lat))]
        new_rows.append(_row(ring_addr, [ring_head, [f"{cluster_name}_ring_{i}"]]))
        poly_addr = f"5-0-{poly_base + i}"
        cluster_poly_addrs.append(poly_addr)
        new_rows.append(_row(poly_addr, [[poly_addr, "~", ring_addr], [f"{cluster_name}_polygon_{i}"]]))
    coll_addr = f"6-0-{coll_base + 1}"  # references the SELECTED PLOT polygons (plot collection)
    new_rows.append(_row(coll_addr, [[coll_addr, "~", *selected_poly_addrs], [f"{cluster_name}_plots"]]))
    feat_addr = f"7-{feat_base + 1}-1"
    hops_day = _hops_day(cts_anchor, day)
    feat_head = [feat_addr, RF_LCL_ID, cluster_node, "1", RF_TITLE, _encode_label_bits(cluster_name),
                 RF_UTC, hops_day, cluster_poly_addrs[0], coll_addr]
    new_rows.append(_row(feat_addr, [feat_head, [cluster_name]]))
    new_fp, fp_hash = _finalize(dataclasses.replace(live["farm_profile"], rows=tuple(new_rows)), "farm_profile")

    # --- persist (lcl + anchor + farm_profile) ----------------------------------------------
    for name, doc, h, is_anchor in (
        ("lcl", new_lcl, lcl_hash, False), ("anchor", new_anchor, anchor_hash, True),
        ("farm_profile", new_fp, fp_hash, False),
    ):
        store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=live[name].document_id, updated_document=doc)
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id, version_hash=h, is_anchor=is_anchor)
    return {"ok": True, "cluster_node": cluster_node, "cluster_name": cluster_name,
            "plots": len(selected_poly_addrs), "outline_parts": len(outline_polys), "feature": feat_addr}
