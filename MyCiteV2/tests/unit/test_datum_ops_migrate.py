"""S4 — pure migration planner (plan_migration) + mint_canonical_id.

Plans a small cross-sheet migration (mint + relocate + recompile + rebuild),
asserts the touched-sheet cascade, re-minted ids, expectations, idempotence,
and that a SAMRAS-inconsistent or dangling plan aborts.
"""

from __future__ import annotations

import unittest

from MyCiteV2.packages.core.datum_ops import (
    MigrationError,
    MintNode,
    RebuildCollection,
    RecompileMagnitude,
    RelocateNode,
    RewriteRefs,
    Workbook,
    labels,
    mint_canonical_id,
    plan_migration,
    samras_deps,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

_NID = labels.RF_NODE_ID
_TITLE = labels.RF_TITLE


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.{name}." + ("a" * 64),
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"agro_erp/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _def(addr: str, node: str, title: str) -> tuple[str, object]:
    return (addr, [[addr, _NID, node, _TITLE, labels.encode_label_bits(title)], [title]])


def _product(addr: str, taxon: str) -> tuple[str, object]:
    return (addr, [[addr, _NID, taxon, "2-1-1", "100"], ["prod"]])


def _wb() -> Workbook:
    # valid single-root tree so SAMRAS recompiles; a genus 1-1 to relocate under.
    node_set = {"1", "1-1", "2", "2-1"}
    bits = samras_deps.build_magnitude_bitstream(node_set)
    txa = _doc("txa", [
        _def("4-2-1", "1", "genus_root"),
        _def("4-2-2", "1-1", "g_child"),
        _def("4-2-3", "2", "catch_all"),
        _def("4-2-4", "2-1", "stray_sp"),
        ("5-0-1", [["5-0-1", "~", "4-2-1", "4-2-2", "4-2-3", "4-2-4"], ["txa_id_collection"]]),
    ])
    anchor = _doc("anchor", [("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]])])
    product = _doc("product_profiles", [_product("4-9-1", "2-1")])
    return Workbook(sandbox="agro_erp", sheets={"anchor": anchor, "txa": txa, "product_profiles": product})


def _renest_ops() -> list[object]:
    # relocate stray_sp (2-1) under genus 1, recompile 1-1-1, rebuild 5-0-1
    return [
        RelocateNode("txa", "2-1", "1"),
        RecompileMagnitude("anchor", "1-1-1", "txa"),
        RebuildCollection("txa", "5-0-1", "txa_id_collection"),
    ]


class MintCanonicalIdTests(unittest.TestCase):
    def test_unchanged_doc_remints_stably(self) -> None:
        doc = _wb().sheet("txa")
        a, _ = mint_canonical_id(doc)
        b, _ = mint_canonical_id(a)
        self.assertEqual(a.document_id, b.document_id)
        self.assertTrue(a.document_id.startswith("lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa."))


class PlanMigrationTests(unittest.TestCase):
    def test_touched_cascade_and_remint(self) -> None:
        wb = _wb()
        plan = plan_migration(wb, _renest_ops())
        # txa (relocate), anchor (recompile), product (ref rewrite) all change
        self.assertEqual(set(plan.touched), {"txa", "anchor", "product_profiles"})
        for name, ts in plan.touched.items():
            self.assertNotEqual(ts.new_document.document_id, ts.prior_id, name)
        # write order puts anchor before txa before product
        self.assertEqual(plan.write_order, ["anchor", "txa", "product_profiles"])
        # the relocated stray_sp (2-1 → 1-2) is now reflected in the product ref
        prod = plan.final_workbook.sheet("product_profiles")
        self.assertEqual(str(prod.rows[0].raw[0][2]), "1-2")

    def test_expectations_recorded(self) -> None:
        plan = plan_migration(_wb(), _renest_ops())
        self.assertIn("1-1-1", plan.expectations["samras"])
        self.assertEqual(plan.expectations["row_counts"]["product_profiles"], 1)

    def test_idempotent_replan_is_noop(self) -> None:
        wb = _wb()
        plan = plan_migration(wb, _renest_ops())
        # re-plan against the already-migrated workbook with the same intent → no change
        replan = plan_migration(plan.final_workbook, [
            RecompileMagnitude("anchor", "1-1-1", "txa"),
            RebuildCollection("txa", "5-0-1", "txa_id_collection"),
        ])
        self.assertEqual(replan.touched, {})

    def test_missing_recompile_aborts(self) -> None:
        wb = _wb()
        # relocate changes the txa node set but we omit RecompileMagnitude → inconsistent
        with self.assertRaises(MigrationError):
            plan_migration(wb, [RelocateNode("txa", "2-1", "1")])

    def test_dangling_reference_aborts(self) -> None:
        wb = _wb()
        with self.assertRaises(MigrationError):
            plan_migration(wb, [RewriteRefs({"2-1": "9-9-9"})])


if __name__ == "__main__":
    unittest.main()
