"""Seed new agro_erp datum docs: livestock / equipment / soil / growing_season (Phase 5).

Creates four new sandbox datum documents (representative seed rows) and the lcl nodes they
need, then recompiles the anchor ``1-1-5`` lcl-SAMRAS. Each new doc is a PAIRS record doc the
generic ``record_table`` viewer (Phase 3 container) paints — proving the "new datum doc → tool"
path is additive. Follows the established discipline (dry-run → backup → write → verify) and is
idempotent (reuse-by-title; refuses to duplicate present docs).

  - livestock  4-3-N: [animal_node(rf.3-1-5), tag(rf.3-1-2), count(rf.3-1-7)]  — animals under lcl 1-1-2
  - equipment  4-3-N: [equip_node(rf.3-1-5), model(rf.3-1-2), cost(rf.3-1-7)]  — new lcl branch 1-7
  - soil       4-3-N: [plot_node(rf.3-1-5), soil_type(rf.3-1-2), acres(rf.3-1-7)] — refs existing plots
  - growing_season 4-3-N: [raunk_node(rf.3-1-1), season(rf.3-1-2), gdd(rf.3-1-7)] — refs existing 1-3-2-5

NOTE: weather/sun ecologicals docs are intentionally NOT seeded — they require an external
data source (a station feed / solar computation) rather than representative seed rows.

Usage:
    python -m MyCiteV2.scripts.seed_agro_erp_new_docs --authority-db DB [--dry-run]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRequest,
)
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    ANCHOR_LCL_SAMRAS,
    NOMINAL_BITS,
    RF_LCL_ID,
    RF_NOMINAL,
    RF_TITLE,
    RF_TXA_ID,
    SANDBOX,
    TENANT,
    LclBuilder,
    _as_rows,
    _build_magnitude_bitstream,
    _encode_label_bits,
    _finalize,
    _hdr,
    _make_new_doc,
    _rebuild_document,
    _row,
    _upsert_documents_row,
)

LCL_ANIMAL = "1-1-2"       # existing "animal" type node under entity 1-1
LCL_EQUIPMENT = "1-7"      # NEW top-level branch (after 1-6 operator_roles)
LCL_PLOT_1, LCL_PLOT_2 = "1-2-2", "1-2-3"   # existing migrated plots
RAUNK = {"therophyte": "1-3-2-5-1", "hemicryptophyte": "1-3-2-5-2", "phanerophytes": "1-3-2-5-3"}

ANIMALS = [("holstein_cow_bessie", "1"), ("rhode_island_red_flock", "12")]
TRACTORS = [("john_deere_5075e", "$45000"), ("kubota_m7_171", "$92000")]
SOIL = [(LCL_PLOT_1, "silt_loam", "1.0"), (LCL_PLOT_2, "clay_loam", "1.0")]
SEASONS = [("therophyte", "spring_summer_annual_window", "2200"),
           ("phanerophytes", "perennial_woody_overwinter", "3600")]

# Each new doc carries this schema token (so document_archetypes recognizes it for the palette).
SCHEMAS = {
    "livestock": "mycite.v2.datum.agro_erp.livestock.v1",
    "equipment": "mycite.v2.datum.agro_erp.equipment.v1",
    "soil": "mycite.v2.datum.agro_erp.soil.v1",
    "growing_season": "mycite.v2.datum.agro_erp.growing_season.v1",
}
NEW_DOCS = tuple(SCHEMAS)


def _record(addr: str, pairs: list[tuple[str, str]], label: str):
    head = [addr]
    for marker, value in pairs:
        head += [marker, value]
    return _row(addr, [head, [label]])


@dataclasses.dataclass
class Plan:
    docs: dict[str, AuthoritativeDatumDocument]
    hashes: dict[str, str]
    prior_ids: dict[str, str | None]
    report: dict


def build(store) -> Plan:
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live: dict[str, AuthoritativeDatumDocument] = {}
    for d in catalog.documents:
        if f".{SANDBOX}." in d.document_id:
            live[d.document_id.split(".")[3]] = d
    for name in ("anchor", "lcl"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found")

    # --- lcl: animal + equipment nodes (reuse-by-title) ----------------------
    lb = LclBuilder(_as_rows(live["lcl"]))
    animal_nodes = [lb.mint_child(LCL_ANIMAL, tag, RF_LCL_ID) for tag, _ in ANIMALS]
    # Mint the equipment branch CONTIGUOUSLY (next child of root) rather than ensuring a
    # hard-coded 1-7: this asserts the SAMRAS contiguous-ordinal invariant holds, so the
    # script can't silently encode a gap if the operator-role branch (1-6) is absent
    # (e.g. reconcile not yet run). Reuse-by-title keeps it idempotent.
    equip_parent = lb.mint_child("1", "equipment", RF_TXA_ID)
    if equip_parent != LCL_EQUIPMENT:
        raise SystemExit(
            f"expected equipment branch {LCL_EQUIPMENT}, minted {equip_parent} — lcl top-level "
            "not contiguous (run reconcile_agro_erp_lcl_entities first to add 1-6); aborting"
        )
    equip_nodes = [lb.mint_child(equip_parent, model, RF_LCL_ID) for model, _ in TRACTORS]
    new_lcl, lcl_hash = _rebuild_document(existing=live["lcl"], overlay=lb.overlay, name="lcl")

    # --- anchor: recompute lcl-SAMRAS ---------------------------------------
    lcl_samras_bits = _build_magnitude_bitstream(lb.node_set)
    anchor_rows = [
        _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_samras_bits], ["lcl-SAMRAS"]])
        if r.datum_address == ANCHOR_LCL_SAMRAS else r
        for r in _as_rows(live["anchor"])
    ]
    new_anchor, anchor_hash = _finalize(dataclasses.replace(live["anchor"], rows=tuple(anchor_rows)), "anchor")

    # --- new docs ------------------------------------------------------------
    def hdrs(name):
        return [_hdr("0-0-1", SCHEMAS[name]), _hdr("0-0-2", SANDBOX)]

    livestock_rows = hdrs("livestock")
    for i, ((tag, count), node) in enumerate(zip(ANIMALS, animal_nodes, strict=True), start=1):
        livestock_rows.append(_record(f"4-3-{i}", [(RF_LCL_ID, node), (RF_TITLE, _encode_label_bits(tag)),
                                                   (RF_NOMINAL, _encode_label_bits(count, bits=NOMINAL_BITS))], tag))

    equipment_rows = hdrs("equipment")
    for i, ((model, cost), node) in enumerate(zip(TRACTORS, equip_nodes, strict=True), start=1):
        equipment_rows.append(_record(f"4-3-{i}", [(RF_LCL_ID, node), (RF_TITLE, _encode_label_bits(model)),
                                                   (RF_NOMINAL, _encode_label_bits(cost, bits=NOMINAL_BITS))], model))

    soil_rows = hdrs("soil")
    for i, (plot, soil_type, acres) in enumerate(SOIL, start=1):
        soil_rows.append(_record(f"4-3-{i}", [(RF_LCL_ID, plot), (RF_TITLE, _encode_label_bits(soil_type)),
                                              (RF_NOMINAL, _encode_label_bits(acres, bits=NOMINAL_BITS))], f"{plot}_{soil_type}"))

    season_rows = hdrs("growing_season")
    for i, (raunk, season, gdd) in enumerate(SEASONS, start=1):
        season_rows.append(_record(f"4-3-{i}", [(RF_TXA_ID, RAUNK[raunk]), (RF_TITLE, _encode_label_bits(season)),
                                               (RF_NOMINAL, _encode_label_bits(gdd, bits=NOMINAL_BITS))], season))

    docs: dict[str, AuthoritativeDatumDocument] = {"anchor": new_anchor, "lcl": new_lcl}
    hashes: dict[str, str] = {"anchor": anchor_hash, "lcl": lcl_hash}
    rowmap = {"livestock": livestock_rows, "equipment": equipment_rows, "soil": soil_rows, "growing_season": season_rows}
    for name, rows in rowmap.items():
        doc, h = _make_new_doc(name, rows, metadata={"schema": SCHEMAS[name], "note": f"agro_erp {name} (seed)"})
        docs[name], hashes[name] = doc, h

    prior_ids = {n: (live[n].document_id if n in live else None) for n in docs}
    report = {
        "lcl_rows_added": len(lb.overlay), "lcl_node_count": len(lb.node_set),
        "animal_nodes": animal_nodes, "equip_nodes": equip_nodes,
        "new_docs": {n: len(rowmap[n]) for n in NEW_DOCS},
    }
    return Plan(docs=docs, hashes=hashes, prior_ids=prior_ids, report=report)


def _verify(authority_db: Path, plan: Plan) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    docs = {d.document_id.split(".")[3]: d for d in cat.documents if f".{SANDBOX}." in d.document_id}
    failures = []
    for name in NEW_DOCS:
        if name not in docs:
            failures.append(f"{name} doc missing after write")
    lcl = docs.get("lcl")
    lcl_nodes = {str(r.raw[0][2]) for r in _as_rows(lcl) if str(r.datum_address).startswith("4-2-") and len(r.raw[0]) >= 3} if lcl else set()
    for n in (LCL_EQUIPMENT, *plan.report["equip_nodes"], *plan.report["animal_nodes"]):
        if n not in lcl_nodes:
            failures.append(f"lcl node {n} not defined")
    # soil/growing_season REFERENCE existing plot / raunkiaerality nodes (not definitions)
    # — confirm those targets actually resolve, else the viewer would show raw addresses.
    for plot, _soil_type, _acres in SOIL:
        if plot not in lcl_nodes:
            failures.append(f"soil references undefined plot node {plot}")
    for raunk, _season, _gdd in SEASONS:
        if RAUNK[raunk] not in lcl_nodes:
            failures.append(f"growing_season references undefined raunk node {RAUNK[raunk]}")
    anchor = docs.get("anchor")
    srow = next((r for r in _as_rows(anchor) if r.datum_address == ANCHOR_LCL_SAMRAS), None) if anchor else None
    denoted = set(decode_canonical_bitstream(str(srow.raw[0][2])).addresses) if srow else set()
    if denoted != lcl_nodes:
        failures.append(f"lcl SAMRAS denoted({len(denoted)}) != defined({len(lcl_nodes)})")
    if failures:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(failures))
    print(f"[verify] PASSED — {len(NEW_DOCS)} new docs live; lcl nodes defined + denoted")


def run(*, authority_db: Path, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    plan = build(store)
    print("\n============ SEED NEW DOCS PLAN ============")
    print(f"lcl rows added : {plan.report['lcl_rows_added']} (node_count={plan.report['lcl_node_count']})")
    for name in NEW_DOCS:
        d = plan.docs[name]
        print(f"  {name:16} rows={len(d.rows):3}  …{d.document_id.split('.')[-1][:12]}  {'(new)' if plan.prior_ids[name] is None else '(CHANGED)'}")
    print("===========================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")
        return {"status": "dry_run", **plan.report}
    if plan.docs["lcl"].document_id == plan.prior_ids["lcl"] and all(plan.prior_ids[n] is not None for n in NEW_DOCS):
        print("[skip] already seeded")
        return {"status": "noop", **plan.report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-seeddocs-{stamp}.bak")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    for name in ("anchor", "lcl", *NEW_DOCS):
        doc = plan.docs[name]
        store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=plan.prior_ids[name], updated_document=doc)
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id, version_hash=plan.hashes[name], is_anchor=(name == "anchor"))
        print(f"[write] {name} → …{doc.document_id.split('.')[-1][:12]}")
    _verify(authority_db, plan)
    return {"status": "applied", "backup": str(backup), **plan.report}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    print(json.dumps(run(authority_db=args.authority_db, dry_run=args.dry_run), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
