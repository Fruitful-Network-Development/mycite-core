#!/usr/bin/env python3
"""Seed the agro_erp TXA taxonomy with the genera the breeding catalogue needs.

``ingest_agro_erp_product_profiles.py`` only nests a species under its genus when
that genus already exists as a TXA title; otherwise it parks the species under the
synthetic catch-all root ``4`` (``agro_unclassified``). The expanded raw catalogue
(97 genus YAML files) introduces 56 species across 22 genera that are absent from
the live taxonomy, so they would catch-all.

This step mints those 22 genera under their real APG-IV families FIRST (minting the
5 absent families under their existing orders), so the subsequent ingest classifies
every species faithfully and nothing lands in the catch-all. It is the same proven
mechanism as ``renest_agro_erp_txa.py``: build a ``datum_ops`` sequence
(``MintNode``/``RecompileMagnitude``/``RebuildCollection``) on a simulated Workbook,
``plan_migration`` (pure, rule-checked), then ``execute_migration`` (backup + verify).

Genus→family and the 5 absent-family→order placements are APG-IV botanical facts,
verified against the live tree (all 4 needed orders — ranunculales, zygophyllales,
malpighiales, gentianales — are present; 6 of the 11 families already exist).

Idempotent: if all 22 genera are already present, the op sequence is empty.

Usage::

    python3 MyCiteV2/scripts/extend_agro_erp_txa_taxonomy.py --authority-db DB [--dry-run] [--apply]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from MyCiteV2.packages.adapters.sql.datum_store import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.adapters.sql.datum_workbook_apply import execute_migration, load_workbook
from MyCiteV2.packages.core.datum_ops import (
    MintNode,
    RebuildCollection,
    RecompileMagnitude,
    Workbook,
    apply_sequence,
    defined_node_addrs,
    plan_migration,
)
from MyCiteV2.packages.core.datum_ops import node_addrs as na

TENANT = "fnd"
SANDBOX = "agro_erp"

ANCHOR_TXA_SAMRAS = "1-1-1"
TXA_COLLECTION = "5-0-1"
TXA_COLLECTION_LABEL = "txa_id_collection"

# The 41 genera the expanded catalogue needs → their APG-IV family (botanical facts,
# verified against the live tree: all host families exist or their order does).
GENUS_FAMILY: dict[str, str] = {
    "asclepias": "apocynaceae",
    "baileya": "asteraceae",
    "blitum": "amaranthaceae",
    "calendula": "asteraceae",
    "centaurea": "asteraceae",
    "chenopodium": "amaranthaceae",
    "cicer": "fabaceae",
    "consolida": "ranunculaceae",
    "corchorus": "malvaceae",
    "coreopsis": "asteraceae",
    "dysphania": "amaranthaceae",
    "echinacea": "asteraceae",
    "encelia": "asteraceae",
    "eriogonum": "polygonaceae",
    "eschscholzia": "papaveraceae",
    "gaillardia": "asteraceae",
    "gossypium": "malvaceae",
    "hyptis": "lamiaceae",
    "indigofera": "fabaceae",
    "kallstroemia": "zygophyllaceae",
    "lens": "fabaceae",
    "linum": "linaceae",
    "lupinus": "fabaceae",
    "machaeranthera": "asteraceae",
    "monarda": "lamiaceae",
    "nicotiana": "solanaceae",
    "oenothera": "onagraceae",
    "oxalis": "oxalidaceae",
    "panicum": "poaceae",
    "papaver": "papaveraceae",
    "penstemon": "plantaginaceae",
    "phacelia": "boraginaceae",
    "ratibida": "asteraceae",
    "rudbeckia": "asteraceae",
    "senna": "fabaceae",
    "smallanthus": "asteraceae",
    "sphaeralcea": "malvaceae",
    "tithonia": "asteraceae",
    "ullucus": "basellaceae",
    "xerochrysum": "asteraceae",
    "zinnia": "asteraceae",
}

# Families absent from the live tree → the existing order they mint under (APG IV).
FAMILY_ORDER: dict[str, str] = {
    "apocynaceae": "gentianales",
    "linaceae": "malpighiales",
    "papaveraceae": "ranunculales",
    "ranunculaceae": "ranunculales",
    "zygophyllaceae": "zygophyllales",
    "onagraceae": "myrtales",
    "oxalidaceae": "oxalidales",
    "plantaginaceae": "lamiales",
}


class _Builder:
    """Builds the op sequence while simulating on a working workbook so minted node
    addresses are visible to ops that reference them (mirrors renest_agro_erp_txa)."""

    def __init__(self, wb: Workbook):
        self.wb = wb
        self.ops: list[object] = []
        self._refresh()

    def _refresh(self) -> None:
        self.title2node: dict[str, str] = {}
        for r in self.wb.sheet("txa").rows:
            raw = r.raw
            if isinstance(raw, list) and len(raw) > 1 and raw[1]:
                self.title2node[str(raw[1][0]).lower()] = str(raw[0][2])

    def _do(self, op) -> None:
        self.ops.append(op)
        self.wb, _ = apply_sequence(self.wb, [op])
        self._refresh()

    def _node_set(self) -> set[str]:
        return defined_node_addrs(self.wb.sheet("txa"))

    def resolve_order(self, order: str) -> str:
        node = self.title2node.get(order)
        if node is None:
            raise SystemExit(f"order {order!r} absent from the live taxonomy — cannot place family")
        return node

    def resolve_family(self, family: str) -> str:
        if family in self.title2node:
            return self.title2node[family]
        order = FAMILY_ORDER.get(family)
        if order is None:
            raise SystemExit(f"family {family!r} absent and no order placement configured")
        order_node = self.resolve_order(order)
        addr = na.next_child(order_node, self._node_set())
        self._do(MintNode("txa", addr, family))
        return addr

    def resolve_genus(self, genus: str, family: str) -> str:
        if genus in self.title2node:
            return self.title2node[genus]
        family_node = self.resolve_family(family)
        addr = na.next_child(family_node, self._node_set())
        self._do(MintNode("txa", addr, genus))
        return addr


def build_ops(baseline: Workbook) -> list[object]:
    b = _Builder(baseline)
    minted_genera: list[tuple[str, str]] = []
    for genus, family in GENUS_FAMILY.items():
        before = b.title2node.get(genus)
        node = b.resolve_genus(genus, family)
        if before is None:
            minted_genera.append((genus, node))
    if not b.ops:
        return []  # idempotent: every genus already present
    # Keep the txa-SAMRAS magnitude + id collection consistent with the new nodes.
    b._do(RecompileMagnitude("anchor", ANCHOR_TXA_SAMRAS, "txa"))
    b._do(RebuildCollection("txa", TXA_COLLECTION, TXA_COLLECTION_LABEL))
    b.minted_genera = minted_genera  # type: ignore[attr-defined]
    return b.ops


def run(*, authority_db: Path, apply: bool) -> dict:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    baseline = load_workbook(store, tenant_id=TENANT, sandbox=SANDBOX)
    builder = _Builder(baseline)  # for reporting which genera/families pre-exist
    ops = build_ops(baseline)

    op_kinds: dict[str, int] = {}
    for op in ops:
        op_kinds[type(op).__name__] = op_kinds.get(type(op).__name__, 0) + 1
    minted = [
        (g, fam) for g, fam in GENUS_FAMILY.items() if g not in builder.title2node
    ]
    minted_families = [
        f for f in FAMILY_ORDER if f not in builder.title2node and f in set(GENUS_FAMILY.values())
    ]

    summary = {
        "ops_total": len(ops),
        "ops_by_kind": op_kinds,
        "genera_to_mint": sorted(g for g, _ in minted),
        "families_to_mint": sorted(minted_families),
        "genera_already_present": sorted(g for g in GENUS_FAMILY if g in builder.title2node),
    }
    if ops:
        plan = plan_migration(baseline, ops)
        summary["touched_sheets"] = sorted(plan.touched)
        summary["new_document_ids"] = {n: ts.new_document.document_id for n, ts in plan.touched.items()}

    print("\n============ TXA TAXONOMY EXTENSION PLAN ============")
    print(json.dumps(summary, indent=2))
    print("====================================================")

    if not ops:
        print(f"No-op: all {len(GENUS_FAMILY)} target genera already present.\n")
        return {"status": "noop", **summary}
    if not apply:
        print("DRY RUN — nothing written.\n")
        return {"status": "dry_run", **summary}

    result = execute_migration(authority_db, plan, tenant_id=TENANT)
    print(json.dumps(result, indent=2))
    return {"status": "applied", **summary, **result}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--authority-db", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if not args.authority_db.exists():
        raise SystemExit(f"authority db missing: {args.authority_db}")
    run(authority_db=args.authority_db, apply=args.apply and not args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
