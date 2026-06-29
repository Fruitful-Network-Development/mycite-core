#!/usr/bin/env python3
"""Add a per-product ``singular_unit_weight`` to product_profiles (horticultural estimates).

The inventory synopsis derives unit counts from purchased weight ÷ the weight of ONE unit
(seed / slip / bulb / root). No such per-unit weight existed, so this appends one — an
APPROXIMATE horticultural estimate keyed by the product's propagule (seed/slip/bulb/root/
splice) refined, for seeds, by its rotation_group crop family. Operator-accepted as
indicative; can later be replaced with measured values by editing the datum.

Each product entry gains a trailing ``(rf.3-1-7, "<g> g")`` nominal, bumping the value group:
``product_profiles 4-9-k (vg9) → 4-10-k (vg10)``. Idempotent; --dry-run default; --apply
backs up + verifies. Mirrors append_record_event_type.py.

Usage::

    python -m MyCiteV2.scripts.add_product_unit_weight --authority-db DB            # dry-run
    python -m MyCiteV2.scripts.add_product_unit_weight --authority-db DB --apply
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import time
from pathlib import Path

from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.core.datum_ops.datum_resolve import cached_index
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest
from MyCiteV2.scripts.ingest_agro_erp_ledger import (
    NOMINAL_BITS,
    SANDBOX,
    TENANT,
    _as_rows,
    _encode_label_bits,
    _finalize,
    _row,
    _upsert_documents_row,
)

RF_NOMINAL = "rf.3-1-7"
OLD_PREFIX = "4-9-"
NEW_PREFIX = "4-10-"
# product_profiles pair positions (0-based): product_id, taxonomy_id, rotation_group,
# propagule, genesis, ownership, raunkiaerality, gestation, spacing.
_ROTATION_VALUE_IDX = 6   # head[2 + 2*2]
_PROPAGULE_VALUE_IDX = 8  # head[2 + 2*3]

# Approximate grams per single unit. Non-seed propagules are flat; seeds vary by crop family.
_PROPAGULE_G: dict[str, float] = {"slip": 5.0, "bulb": 20.0, "root": 30.0, "splice": 10.0}
_SEED_G_BY_FAMILY: dict[str, float] = {
    "legumes": 0.3, "nightshades": 0.003, "brassicas": 0.004, "alliums": 0.004,
    "umbellifers": 0.0013, "cucurbits": 0.15, "leafy_greens": 0.0011, "chenopods": 0.012,
    "grasses": 0.03, "mallow_family": 0.07, "mint_family": 0.0008, "sweet_potato": 5.0,
    "composites": 0.006, "other": 0.01,
}
_DEFAULT_SEED_G = 0.01


def estimate_grams(propagule: str, rotation_group: str) -> float:
    p = (propagule or "").strip().lower()
    if p in _PROPAGULE_G:
        return _PROPAGULE_G[p]
    return _SEED_G_BY_FAMILY.get((rotation_group or "").strip().lower(), _DEFAULT_SEED_G)


def _fmt(grams: float) -> str:
    return f"{grams:g} g"


def run(*, authority_db: Path, dry_run: bool) -> dict:
    if not authority_db.exists():
        raise SystemExit(f"authority db missing: {authority_db}")
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    live = {d.document_id.split(".")[3]: d for d in catalog.documents if f".{SANDBOX}." in d.document_id}
    pp = live.get("product_profiles")
    if pp is None:
        raise SystemExit("agro_erp.product_profiles not found")
    lcl = cached_index(live.get("lcl"))

    rows = _as_rows(pp)
    if any(r.datum_address.startswith(NEW_PREFIX) for r in rows):
        print("product_profiles already migrated (4-10-* present) — skip")
        return {"status": "noop"}

    kept = [r for r in rows if not r.datum_address.startswith(OLD_PREFIX)]
    moved: list = []
    samples: list[tuple[str, str, str]] = []
    for r in rows:
        if not r.datum_address.startswith(OLD_PREFIX):
            continue
        k = r.datum_address[len(OLD_PREFIX):]
        new_addr = f"{NEW_PREFIX}{k}"
        head = list(r.raw[0])
        rg = lcl.resolve(str(head[_ROTATION_VALUE_IDX])) if len(head) > _ROTATION_VALUE_IDX else ""
        prop = lcl.resolve(str(head[_PROPAGULE_VALUE_IDX])) if len(head) > _PROPAGULE_VALUE_IDX else ""
        grams = estimate_grams(prop, rg)
        head[0] = new_addr
        head = [*head, RF_NOMINAL, _encode_label_bits(_fmt(grams), bits=NOMINAL_BITS)]
        moved.append(_row(new_addr, [head, *list(r.raw)[1:]]))
        if len(samples) < 5:
            samples.append((prop or "?", rg or "?", _fmt(grams)))

    new_pp, h = _finalize(dataclasses.replace(pp, rows=tuple([*kept, *moved])), "product_profiles")
    report = {"products": len(moved), "samples": samples,
              "prior_id": pp.document_id, "document_id": new_pp.document_id}
    print("\n===== ADD PRODUCT singular_unit_weight =====")
    print(f"  products migrated 4-9-*→4-10-* : {len(moved)}")
    print(f"  sample (propagule, family → est): {samples}")
    print("============================================")
    if dry_run:
        print("DRY RUN — nothing written.\n")
        return {"status": "dry_run", **report}

    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup = authority_db.with_name(authority_db.name + f".pre-unitweight-{stamp}.bak")
    if backup.exists():
        raise SystemExit(f"backup target already exists: {backup}")
    shutil.copy2(authority_db, backup)
    print(f"[backup] {backup}")
    store.replace_single_document_efficient(tenant_id=TENANT, prior_document_id=pp.document_id, updated_document=new_pp)
    _upsert_documents_row(authority_db, name="product_profiles", document_id=new_pp.document_id, version_hash=h, is_anchor=False)
    print(f"[write] product_profiles → …{new_pp.document_id.split('.')[-1][:14]}")
    _verify(authority_db, expect=len(moved))
    return {"status": "applied", "backup": str(backup), **report}


def _verify(authority_db: Path, *, expect: int) -> None:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    catalog = store.read_authoritative_datum_documents(AuthoritativeDatumDocumentRequest(tenant_id=TENANT))
    pp = next((d for d in catalog.documents if ".agro_erp.product_profiles." in d.document_id), None)
    rows = _as_rows(pp) if pp else []
    new_rows = [r for r in rows if r.datum_address.startswith(NEW_PREFIX)]
    stale = [r for r in rows if r.datum_address.startswith(OLD_PREFIX)]
    fails = []
    if stale:
        fails.append(f"{len(stale)} stale 4-9-* rows remain")
    if len(new_rows) != expect:
        fails.append(f"{len(new_rows)} 4-10-* rows, expected {expect}")
    # every new row must carry the trailing nominal
    for r in new_rows:
        head = r.raw[0]
        if not (len(head) >= 2 and str(head[-2]).lower() == RF_NOMINAL):
            fails.append(f"{r.datum_address}: missing unit-weight nominal")
            break
    if fails:
        raise SystemExit("POST-WRITE VERIFY FAILED:\n  " + "\n  ".join(fails))
    print(f"[verify] PASSED — {len(new_rows)} products carry singular_unit_weight")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="write (default is a dry-run)")
    args = ap.parse_args(argv)
    print(json.dumps(run(authority_db=args.authority_db, dry_run=not args.apply), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
