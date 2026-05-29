#!/usr/bin/env python3
"""Re-nest the agro_erp TXA catch-all taxonomy THROUGH the datum_ops library.

The agro_erp ``txa`` document has 36 species/junk leaves wrongly parked under the
synthetic catch-all root ``4`` (``agro_unclassified``). This happened because the
ingestion resolver only nests a species under a genus when the YAML ``genus_group``
field is already a TXA title — and these came from ``unknown_genus.yaml``. Their
real (internet-verified) taxonomy is in
``/srv/agentic/evidence/portal-visualizer-cutover/txa_catchall_taxonomy.md``.

This script is the **acceptance harness** for the datum-workbook library: it loads
the agro_erp sandbox as a :class:`Workbook`, builds the re-nesting op sequence using
ONLY the rudimentary ops (``MintNode``/``RelocateNode``/``RepointNode``/``RenameNode``/
``DropNode``/``RecompileMagnitude``/``RebuildCollection``), plans the migration
(pure, rule-checked), and applies it via the store-bound executor (backup + verify).

End state: the 31 real binomials nest under their genus (minting 26 genera + the
absent ``caprifoliaceae`` family); the 2 ``_spp.`` aggregates fold into their genus;
``direct``/``mixed_spp.`` products re-point to a single ``unspecified`` bucket (the
renamed ``unknown`` node, which renumbers to ``4-1``); ``1-1-1`` (txa-SAMRAS) and
``5-0-1`` (id collection) recompile; anchor/txa/product_profiles ids re-mint.

Usage::

    python3 MyCiteV2/scripts/renest_agro_erp_txa.py --authority-db DB [--dry-run] [--apply]
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
    DropNode,
    MintNode,
    RebuildCollection,
    RecompileMagnitude,
    RelocateNode,
    RenameNode,
    RepointNode,
    Workbook,
    apply_sequence,
    defined_node_addrs,
    plan_migration,
)
from MyCiteV2.packages.core.datum_ops import node_addrs as na

TENANT = "fnd"
SANDBOX = "agro_erp"

# 31 real binomials wrongly catch-alled → (genus, family). (internet-verified)
TAXONOMY: dict[str, tuple[str, str]] = {
    "arctium_lappa": ("arctium", "asteraceae"),
    "armoracia_rusticana": ("armoracia", "brassicaceae"),
    "physalis_pruinosa": ("physalis", "solanaceae"),
    "physalis_philadelphica": ("physalis", "solanaceae"),
    "pisum_sativum": ("pisum", "fabaceae"),
    "scorzonera_hispanica": ("scorzonera", "asteraceae"),
    "tragopogon_porrifolius": ("tragopogon", "asteraceae"),
    "brassica_carinata": ("brassica", "brassicaceae"),
    "diplotaxis_tenuifolia": ("diplotaxis", "brassicaceae"),
    "basella_rubra": ("basella", "basellaceae"),
    "valerianella_locusta": ("valerianella", "caprifoliaceae"),
    "nasturtium_officinale": ("nasturtium", "brassicaceae"),
    "rumex_sanguineus": ("rumex", "polygonaceae"),
    "atriplex_hortensis": ("atriplex", "amaranthaceae"),
    "claytonia_perfoliata": ("claytonia", "montiaceae"),
    "amaranthus_tricolor": ("amaranthus", "amaranthaceae"),
    "glebionis_coronaria": ("glebionis", "asteraceae"),
    "anthriscus_cerefolium": ("anthriscus", "apiaceae"),
    "medicago_sativa": ("medicago", "fabaceae"),
    "ocimum_basilicum_citriodora": ("ocimum", "lamiaceae"),
    "lepidium_sativum": ("lepidium", "brassicaceae"),
    "portulaca_oleracea": ("portulaca", "portulacaceae"),
    "agastache_foeniculum": ("agastache", "lamiaceae"),
    "celosia_argentea_plumosa": ("celosia", "amaranthaceae"),
    "tagetes_tenuifolia": ("tagetes", "asteraceae"),
    "perilla_frutescens": ("perilla", "lamiaceae"),
    "tropaeolum_majus": ("tropaeolum", "tropaeolaceae"),
    "triticum_aestivum": ("triticum", "poaceae"),
    "tropaeolum_minus": ("tropaeolum", "tropaeolaceae"),
    "vigna_radiata": ("vigna", "fabaceae"),
    "trigonella_foenum_graecum": ("trigonella", "fabaceae"),
}
# genus-level aggregates folded onto their genus node (then their leaf is dropped)
AGGREGATES: dict[str, tuple[str, str]] = {
    "amaranthus_spp.": ("amaranthus", "amaranthaceae"),
    "allium_spp": ("allium", "amaryllidaceae"),
}
JUNK = ("direct", "mixed_spp.")             # products re-pointed to unspecified, leaf dropped
SURVIVOR_TITLE = "unknown"                   # kept as the single 'unspecified' bucket
SURVIVOR_NEW_TITLE = "unspecified"
# Caprifoliaceae (Dipsacales) is absent; mint it as a sibling family of asteraceae
# (both campanulid asterids) — valid SAMRAS placement, out of agro_unclassified.
FAMILY_MINT_UNDER_SIBLING = {"caprifoliaceae": "asteraceae"}

ANCHOR_TXA_SAMRAS = "1-1-1"
TXA_COLLECTION = "5-0-1"
TXA_COLLECTION_LABEL = "txa_id_collection"


class _Builder:
    """Builds the op sequence while simulating on a working workbook so minted
    node addresses are known to the ops that reference them."""

    def __init__(self, wb: Workbook):
        self.wb = wb
        self.ops: list[object] = []
        self._refresh()

    def _refresh(self) -> None:
        self.title2node = {}
        self.node2title = {}
        for r in self.wb.sheet("txa").rows:
            raw = r.raw
            if isinstance(raw, list) and len(raw) > 1 and raw[1]:
                t = str(raw[1][0]).lower()
                n = str(raw[0][2])
                self.title2node[t] = n
                self.node2title[n] = t

    def _do(self, op) -> None:
        self.ops.append(op)
        self.wb, _ = apply_sequence(self.wb, [op])
        self._refresh()

    def _node_set(self) -> set[str]:
        return defined_node_addrs(self.wb.sheet("txa"))

    def resolve_family(self, family: str) -> str:
        if family in self.title2node:
            return self.title2node[family]
        sibling = FAMILY_MINT_UNDER_SIBLING.get(family)
        if sibling is None or sibling not in self.title2node:
            raise SystemExit(f"family {family!r} absent and no mint parent configured")
        order_node = na.parent_of(self.title2node[sibling])  # the order group
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

    # locate the 36 catch-all leaves (4-1..4-N) by current address
    catch_all = {n: t for n, t in b.node2title.items() if n.startswith("4-") and na.parent_of(n) == "4"}
    # idempotency guard: already re-nested (the survivor was renamed → no 'unknown' leaf)
    if not any(t == SURVIVOR_TITLE for t in catch_all.values()):
        return []
    survivor_node = next(n for n, t in catch_all.items() if t == SURVIVOR_TITLE)

    # A. mint every genus needed (and the absent family), de-duplicated
    genus_node: dict[str, str] = {}
    for _title, (genus, family) in {**TAXONOMY, **AGGREGATES}.items():
        if genus not in genus_node:
            genus_node[genus] = b.resolve_genus(genus, family)

    # B. rename the survivor 'unknown' → 'unspecified'
    b._do(RenameNode("txa", survivor_node, SURVIVOR_NEW_TITLE))

    # C. re-point junk products (direct/mixed_spp.) to the survivor (still at its addr)
    for n, t in catch_all.items():
        if t in JUNK:
            b._do(RepointNode("txa", n, survivor_node))

    # D. fold the aggregates onto their genus node
    for n, t in catch_all.items():
        if t in AGGREGATES:
            b._do(RepointNode("txa", n, genus_node[AGGREGATES[t][0]]))

    # E. descending pass over the catch-all leaves (skip the survivor): relocate
    #    binomials under their genus; drop the now-unreferenced junk/aggregate leaves.
    #    Descending ordinal → each removal is the trailing root-4 child (no churn);
    #    the survivor renumbers down to 4-1 as everything below it leaves.
    for n in sorted(catch_all, key=lambda x: int(x.split("-")[1]), reverse=True):
        t = catch_all[n]
        if n == survivor_node:
            continue
        if t in TAXONOMY:
            b._do(RelocateNode("txa", n, genus_node[TAXONOMY[t][0]]))
        elif t in AGGREGATES or t in JUNK:
            b._do(DropNode("txa", n))
        else:
            raise SystemExit(f"unclassified catch-all leaf: {n} {t!r}")

    # F. housekeeping: recompile the txa-SAMRAS magnitude + rebuild the id collection
    b._do(RecompileMagnitude("anchor", ANCHOR_TXA_SAMRAS, "txa"))
    b._do(RebuildCollection("txa", TXA_COLLECTION, TXA_COLLECTION_LABEL))
    return b.ops


def run(*, authority_db: Path, apply: bool) -> dict:
    store = SqliteSystemDatumStoreAdapter(authority_db, allow_legacy_writes=False)
    baseline = load_workbook(store, tenant_id=TENANT, sandbox=SANDBOX)
    ops = build_ops(baseline)
    plan = plan_migration(baseline, ops)

    final_txa = plan.final_workbook.sheet("txa")
    catch_all_after = sorted(
        n for n in defined_node_addrs(final_txa) if n == "4" or na.parent_of(n) == "4"
    )
    op_kinds: dict[str, int] = {}
    for op in ops:
        op_kinds[type(op).__name__] = op_kinds.get(type(op).__name__, 0) + 1

    summary = {
        "ops_total": len(ops),
        "ops_by_kind": op_kinds,
        "touched_sheets": sorted(plan.touched),
        "catch_all_after": catch_all_after,
        "new_document_ids": {n: ts.new_document.document_id for n, ts in plan.touched.items()},
    }
    print("\n================ RE-NEST PLAN ================")
    print(json.dumps(summary, indent=2))
    print("=============================================")

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
