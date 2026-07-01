#!/usr/bin/env python3
"""Rectify the LCL product-node sprawl — cultivars → TXA variety nodes, products → arbitrary product_N.

`ingest_agro_erp_product_profiles.py` minted one LCL product node PER raw row, each TITLED with the full
`species-cultivar` key (e.g. ``abelmoschus_esculentus-clemson_spineless``), giving 4,483 unrequested product
nodes in the SAMRAS structure plus a handful of hyphenated TXA leaks. The operator's model:

  * TXA carries cultivars as **variety-rank children** of the species (``species → var.<cultivar>``).
  * LCL ``1-3-1 product_type`` holds **arbitrary ``product_N``** ids — one per cultivar that has a complete
    profile (the most-specific node with data; a bare species gets none).
  * ``4-9`` profiles repoint ``taxonomy_id`` → the variety node and ``product_id`` → ``product_N``; the tail
    becomes the derived scientific title. Profiles with no collected data are DEFERRED (recorded, not minted).

This script works ENTIRELY FROM THE LIVE MOS (the raw catalogue was archived) — cultivar = the suffix of the
``4-9`` tail key, species = the existing ``taxonomy_id``. Scientific title is derived; common name is deferred.
"Complete data" = ``gestation > 0`` (the operator's threshold). It reuses the canonical ingest machinery
(``_build_magnitude_bitstream``, ``_rebuild_document(drop=)``, ``_encode_label_bits``) and follows the standing
discipline: dry-run on an isolated copy, back up the live DB, self-verify, gate the live write.

Usage::

    rectify_agro_erp_product_lcl.py --db <copy>                 # DRY-RUN (writes the deferred list only)
    rectify_agro_erp_product_lcl.py --db <copy> --apply         # write (backs up first)
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

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.scripts.ingest_agro_erp_product_profiles import (
    ANCHOR_LCL_SAMRAS,
    ANCHOR_TXA_SAMRAS,
    ANCHOR_UNIT_SECOND_ABS,
    LCL_PRODUCT_TYPE,
    RF_LCL_ID,
    RF_TITLE,
    RF_TXA_ID,
    SANDBOX,
    TENANT,
    _as_rows,
    _build_magnitude_bitstream,
    _encode_label_bits,
    _rebuild_document,
    _row,
    _upsert_documents_row,
)

RF312_BYTES = 64  # 512-bit title babelette → ≤64 ASCII chars
_DEFERRED_OUT_DEFAULT = "/srv/agentic/evidence/agro-product-lcl-rectify/deferred_profiles.txt"


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def _head(r) -> list[str]:
    return [str(t).strip() for t in r.raw[0]]


def _tail(r) -> str:
    return str(r.raw[1][0]).strip() if len(r.raw) > 1 and r.raw[1] else ""


def _label_for_encoding(label: str) -> str:
    """≤64-char ASCII-safe label for the 512-bit title babelette (drop a doubled tail, else truncate)."""
    enc = label.encode("ascii", errors="ignore").decode("ascii")
    if len(enc) <= RF312_BYTES:
        return enc
    head = enc.rsplit("-", 1)[0]
    return head[:RF312_BYTES] if len(head) > RF312_BYTES else head


def _scientific_title(species_title: str, cultivar: str) -> str:
    """Derive 'Genus species' + optional "'Cultivar'" from the underscore-joined TXA titles."""
    parts = species_title.split("_")
    binomial = " ".join(p.capitalize() if i == 0 else p.lower() for i, p in enumerate(parts))
    if not cultivar:
        return binomial
    cult = " ".join(w.capitalize() for w in cultivar.split("_"))
    return f"{binomial} '{cult}'"


def _profile_pairs(head: list[str]) -> list[tuple[str, str]]:
    return [(head[i], head[i + 1]) for i in range(1, len(head) - 1, 2)]


def _value_after(head: list[str], marker: str) -> str | None:
    for m, v in _profile_pairs(head):
        if m == marker:
            return v
    return None


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class _Profile:
    addr: str
    head: list[str]
    species: str
    cultivar: str          # "" when the key is a bare species
    gestation: int
    key: str               # the original species-cultivar tail


def _parse_profiles(pp_rows) -> list[_Profile]:
    out: list[_Profile] = []
    for r in pp_rows:
        head = _head(r)
        species = _value_after(head, RF_TXA_ID) or "0"   # FIRST rf.3-1-1 pair = taxonomy_id
        key = _tail(r)
        cultivar = key.split("-", 1)[1] if "-" in key else ""
        gest = _value_after(head, ANCHOR_UNIT_SECOND_ABS) or "0"
        try:
            gest_i = int(gest)
        except ValueError:
            gest_i = 0
        out.append(_Profile(addr=r.datum_address, head=head, species=species,
                            cultivar=cultivar, gestation=gest_i, key=key))
    return out


def _child_max_index(nodes: set[str]) -> dict[str, int]:
    cm: dict[str, int] = {}
    for n in nodes:
        if "-" in n:
            parent, ordn = n.rsplit("-", 1)
            try:
                cm[parent] = max(cm.get(parent, 0), int(ordn))
            except ValueError:
                continue
    return cm


def build(store: SqliteSystemDatumStoreAdapter, *, gestation_min: int, deferred_out: Path):
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in cat.documents if f".{SANDBOX}." in d.document_id}
    for name in ("anchor", "txa", "lcl", "product_profiles"):
        if name not in live:
            raise SystemExit(f"live agro_erp.{name} not found")
    # GUARD: product_profiles was migrated to vg-10 (4-10-*) by add_product_unit_weight.py. This
    # script builds/drops at the OLD 4-9- prefix, so re-running it now would leave the migrated
    # 4-10-* rows untouched and write a second 4-9- product block (the viewers read only 4-10-).
    if any(r.datum_address.startswith("4-10-") for r in _as_rows(live["product_profiles"])):
        raise SystemExit(
            "product_profiles is at vg-10 (4-10-*, singular_unit_weight migration applied); "
            "this 4-9- rectify is SUPERSEDED — revert the unit-weight migration before re-running, "
            "or update this script to vg-10 first."
        )

    txa_rows = _as_rows(live["txa"])
    lcl_rows = _as_rows(live["lcl"])
    pp_rows = [r for r in _as_rows(live["product_profiles"]) if r.datum_address.startswith("4-9-")]

    # --- TXA current state: node set, titles, def-address per node, child ordinals -----------------
    txa_title: dict[str, str] = {}
    txa_node_def: dict[str, str] = {}     # node -> its 4-2-* def address
    txa_nodes: set[str] = set()
    txa_max_42 = 0
    for r in txa_rows:
        if not r.datum_address.startswith("4-2-"):
            continue
        txa_max_42 = max(txa_max_42, int(r.datum_address.split("-")[2]))
        h = _head(r)
        if len(h) > 2:
            node = h[2]
            txa_nodes.add(node)
            txa_title[node] = _tail(r)
            txa_node_def[node] = r.datum_address
    txa_child_max = _child_max_index(txa_nodes)
    # index existing direct children of a species by (parent, title.lower()) for variety reuse
    child_by_title: dict[tuple[str, str], str] = {}
    for node, title in txa_title.items():
        if "-" in node:
            parent = node.rsplit("-", 1)[0]
            child_by_title[(parent, title.lower())] = node

    # 9 hyphenated TXA leaks (species-cultivar titled variety nodes) → re-title to the cultivar suffix.
    leak_nodes = {n: t for n, t in txa_title.items() if "-" in t}

    # --- partition profiles ----------------------------------------------------------------------
    profiles = _parse_profiles(pp_rows)
    kept: list[_Profile] = []
    deferred: list[tuple[str, str]] = []   # (key, reason)
    for p in profiles:
        if p.species == "0" or p.species not in txa_nodes:
            deferred.append((p.key, "unresolved_species"))
        elif p.gestation < gestation_min:
            deferred.append((p.key, f"gestation<{gestation_min}"))
        else:
            kept.append(p)

    # --- TXA: ensure a variety node per kept (species, cultivar) ----------------------------------
    txa_overlay: dict = {}
    variety_node: dict[tuple[str, str], str] = {}
    minted_varieties: list[tuple[str, str]] = []
    next_42 = txa_max_42 + 1

    def _mint_variety(species: str, cultivar: str) -> str:
        key = (species, cultivar.lower())
        if key in variety_node:
            return variety_node[key]
        existing = child_by_title.get(key)
        if existing:                       # already a clean variety child
            variety_node[key] = existing
            return existing
        nonlocal next_42
        ordn = txa_child_max.get(species, 0) + 1
        txa_child_max[species] = ordn
        node = f"{species}-{ordn}"
        txa_overlay[f"4-2-{next_42}"] = _row(
            f"4-2-{next_42}", [[f"4-2-{next_42}", RF_TXA_ID, node, RF_TITLE, _encode_label_bits(_label_for_encoding(cultivar))], [cultivar]]
        )
        next_42 += 1
        txa_nodes.add(node)
        variety_node[key] = node
        child_by_title[key] = node
        minted_varieties.append((node, cultivar))
        return node

    for p in kept:
        p_variety = _mint_variety(p.species, p.cultivar) if p.cultivar else p.species
        p.variety = p_variety  # type: ignore[attr-defined]

    # re-title the hyphenated leaks in place (node kept; title → cultivar suffix). Safe: leak nodes are
    # variety-level and not referenced as a profile taxonomy_id (asserted below).
    retitled_leaks: list[tuple[str, str]] = []
    leak_referenced = [p.key for p in kept if p.species in leak_nodes]
    for node, title in leak_nodes.items():
        cult = title.split("-", 1)[1] if "-" in title else title
        txa_overlay[txa_node_def[node]] = _row(
            txa_node_def[node], [[txa_node_def[node], RF_TXA_ID, node, RF_TITLE, _encode_label_bits(_label_for_encoding(cult))], [cult]]
        )
        retitled_leaks.append((node, cult))

    # rebuild the 5-0-1 txa_id_collection over the post-overlay def-address set
    txa_def_addrs = {r.datum_address for r in txa_rows if r.datum_address.startswith("4-2-")} | set(txa_overlay)
    txa_overlay["5-0-1"] = _row("5-0-1", [["5-0-1", "~", *sorted(txa_def_addrs, key=lambda a: int(a.split("-")[2]))], ["txa_id_collection"]])
    new_txa, txa_hash = _rebuild_document(existing=live["txa"], overlay=txa_overlay, drop=lambda a: False, name="txa")

    # --- LCL: drop the 4,483 species-cultivar product defs, mint product_2..product_{1+K} ----------
    old_product_nodes = {h[2] for r in lcl_rows if r.datum_address.startswith("4-2-")
                         and (h := _head(r)) and len(h) > 2 and h[2].startswith(LCL_PRODUCT_TYPE + "-")
                         and h[2] != f"{LCL_PRODUCT_TYPE}-1"}
    lcl_nodes = {h[2] for r in lcl_rows if r.datum_address.startswith("4-2-") and (h := _head(r)) and len(h) > 2}
    lcl_max_42 = max(int(r.datum_address.split("-")[2]) for r in lcl_rows if r.datum_address.startswith("4-2-"))
    lcl_overlay: dict = {}
    product_node: dict[str, str] = {}     # profile addr -> new lcl product node
    next_lcl_42 = lcl_max_42 + 1
    new_product_nodes: set[str] = set()
    for i, p in enumerate(kept, start=2):  # product_1 (1-3-1-1) is kept; new products start at 2
        node = f"{LCL_PRODUCT_TYPE}-{i}"
        label = f"product_{i}"
        product_node[p.addr] = node
        new_product_nodes.add(node)
        lcl_overlay[f"4-2-{next_lcl_42}"] = _row(
            f"4-2-{next_lcl_42}", [[f"4-2-{next_lcl_42}", RF_LCL_ID, node, RF_TITLE, _encode_label_bits(label)], [label]]
        )
        next_lcl_42 += 1
    old_product_def_addrs = {r.datum_address for r in lcl_rows if r.datum_address.startswith("4-2-")
                             and (h := _head(r)) and len(h) > 2 and h[2].startswith(LCL_PRODUCT_TYPE + "-")
                             and h[2] != f"{LCL_PRODUCT_TYPE}-1"}
    new_lcl, lcl_hash = _rebuild_document(
        existing=live["lcl"], overlay=lcl_overlay, drop=lambda a: a in old_product_def_addrs, name="lcl"
    )
    new_lcl_nodes = (lcl_nodes - old_product_nodes) | new_product_nodes

    # --- product_profiles: rebuild kept rows (repoint product_id + taxonomy_id; tail = scientific) --
    pp_overlay: dict = {}
    for j, p in enumerate(kept, start=1):
        addr = f"4-9-{j}"
        h = list(p.head)
        h[0] = addr
        # replace the product_id value (after the single RF_LCL_ID) and the FIRST taxonomy value
        for i in range(1, len(h) - 1, 2):
            if h[i] == RF_LCL_ID:
                h[i + 1] = product_node[p.addr]
                break
        for i in range(1, len(h) - 1, 2):
            if h[i] == RF_TXA_ID:
                h[i + 1] = p.variety  # type: ignore[attr-defined]
                break
        sci = _scientific_title(txa_title.get(p.species, p.species), p.cultivar)
        pp_overlay[addr] = _row(addr, [h, [sci]])
    new_pp, pp_hash = _rebuild_document(
        existing=live["product_profiles"], overlay=pp_overlay, drop=lambda a: a.startswith("4-9-"), name="product_profiles"
    )

    # --- anchor: recompute txa-SAMRAS (1-1-1) + lcl-SAMRAS (1-1-5) over the new node sets ----------
    txa_bits = _build_magnitude_bitstream(txa_nodes)
    lcl_bits = _build_magnitude_bitstream(new_lcl_nodes)
    anchor_overlay = {
        ANCHOR_TXA_SAMRAS: _row(ANCHOR_TXA_SAMRAS, [[ANCHOR_TXA_SAMRAS, "0-0-5", txa_bits], ["txa-SAMRAS"]]),
        ANCHOR_LCL_SAMRAS: _row(ANCHOR_LCL_SAMRAS, [[ANCHOR_LCL_SAMRAS, "0-0-5", lcl_bits], ["lcl-SAMRAS"]]),
    }
    new_anchor, anchor_hash = _rebuild_document(existing=live["anchor"], overlay=anchor_overlay, drop=lambda a: False, name="anchor")

    # --- deferred artifact ------------------------------------------------------------------------
    deferred_out.parent.mkdir(parents=True, exist_ok=True)
    deferred_out.write_text("\n".join(f"{k}\t{reason}" for k, reason in deferred) + ("\n" if deferred else ""))

    report = {
        "profiles_total": len(profiles),
        "kept(gestation>0)": len(kept),
        "deferred": len(deferred),
        "deferred_out": str(deferred_out),
        "txa_varieties_minted": len(minted_varieties),
        "txa_leaks_retitled": len(retitled_leaks),
        "txa_node_count": len(txa_nodes),
        "lcl_old_product_nodes_dropped": len(old_product_nodes),
        "lcl_new_product_nodes": len(new_product_nodes),
        "lcl_node_count": len(new_lcl_nodes),
        "leak_referenced_by_profiles": leak_referenced,
    }
    docs = {"anchor": new_anchor, "txa": new_txa, "lcl": new_lcl, "product_profiles": new_pp}
    hashes = {"anchor": anchor_hash, "txa": txa_hash, "lcl": lcl_hash, "product_profiles": pp_hash}
    prior = {n: live[n].document_id for n in docs}
    return docs, prior, hashes, report


def _verify_post_write(authority_db: Path, *, expect_products: int) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    cat = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in cat.documents if f".{SANDBOX}." in d.document_id}
    fails: list[str] = []
    # no species-cultivar titled LCL product nodes remain
    bad = [_tail(r) for r in live["lcl"].rows if r.datum_address.startswith("4-2-")
           and (h := _head(r)) and len(h) > 2 and h[2].startswith(LCL_PRODUCT_TYPE + "-") and "-" in _tail(r)]
    if bad:
        fails.append(f"{len(bad)} species-cultivar LCL nodes still present (e.g. {bad[:3]})")
    prods = [_tail(r) for r in live["lcl"].rows if r.datum_address.startswith("4-2-")
             and (h := _head(r)) and len(h) > 2 and h[2].startswith(LCL_PRODUCT_TYPE + "-")]
    n_prod = sum(1 for t in prods if t.startswith("product_"))
    if n_prod != expect_products + 1:  # +1 for the kept product_1
        fails.append(f"LCL product_N count={n_prod}, expected {expect_products + 1}")
    if fails:
        raise SystemExit("[verify FAILED] " + "; ".join(fails))
    print(f"[verify] {n_prod} product_N nodes, 0 species-cultivar nodes remain")


def run(*, authority_db: Path, gestation_min: int, deferred_out: Path, dry_run: bool) -> dict:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    docs, prior, hashes, report = build(store, gestation_min=gestation_min, deferred_out=deferred_out)
    print("== rectify product/LCL ==")
    for k, v in report.items():
        print(f"  {k}: {v if not isinstance(v, list) else v[:5]}")
    for name, doc in docs.items():
        tag = "(unchanged)" if doc.document_id == prior[name] else "(CHANGED)"
        print(f"  {name:18} rows={len(doc.rows):5} {tag}")
    if dry_run:
        print("DRY RUN — nothing written (deferred list WAS written for inspection).")
        return report
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-productlcl-{stamp}.bak")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    for name, doc in docs.items():
        if doc.document_id == prior[name]:
            continue
        store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=prior[name], updated_document=doc)
        _upsert_documents_row(authority_db, name=name, document_id=doc.document_id,
                              version_hash=hashes[name], is_anchor=(name == "anchor"))
    print("[applied]")
    _verify_post_write(authority_db, expect_products=report["kept(gestation>0)"])
    return report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Rectify LCL product sprawl: cultivars→TXA varieties, products→product_N.")
    ap.add_argument("--db", required=True)
    ap.add_argument("--gestation-min", type=int, default=1, help="min gestation seconds to count as data-complete (default 1)")
    ap.add_argument("--deferred-out", default=_DEFERRED_OUT_DEFAULT)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    run(authority_db=Path(args.db), gestation_min=args.gestation_min,
        deferred_out=Path(args.deferred_out), dry_run=not args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
