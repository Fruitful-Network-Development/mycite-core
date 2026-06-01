"""S3 — node-address ops, ref rewrite, SAMRAS recompile, rule loop.

Relocate/drop/repoint exercise the node-address remap + cross-sheet reference
cascade; RecompileMagnitude + check_step exercise the SAMRAS roundtrip and the
dangling-reference gate.
"""

from __future__ import annotations

import unittest

from MyCiteV2.packages.core.datum_ops import (
    DropNode,
    MintNode,
    RebuildCollection,
    RecompileMagnitude,
    RelocateNode,
    RenameNode,
    RepointNode,
    RewriteRefs,
    Workbook,
    build_reference_index,
    check_step,
    defined_node_addrs,
    labels,
    samras_deps,
)
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

_TITLE = labels.RF_TITLE
_NID = labels.RF_NODE_ID


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


def _catch_all_wb() -> Workbook:
    txa = _doc("txa", [
        _def("4-2-1", "1", "cytota"),
        _def("4-2-2", "1-3", "brassicaceae"),
        _def("4-2-3", "4", "agro_unclassified"),
        _def("4-2-4", "4-1", "sp_a"),
        _def("4-2-5", "4-2", "sp_b"),
        _def("4-2-6", "4-3", "sp_c"),
        ("5-0-1", [["5-0-1", "~", "4-2-1", "4-2-2", "4-2-3", "4-2-4", "4-2-5", "4-2-6"], ["txa_id_collection"]]),
    ])
    product = _doc("product_profiles", [
        _product("4-9-1", "4-1"),
        _product("4-9-2", "4-2"),
        _product("4-9-3", "4-3"),
    ])
    return Workbook(sandbox="agro_erp", sheets={"txa": txa, "product_profiles": product})


def _taxon_of(doc: AuthoritativeDatumDocument, addr: str) -> str:
    row = next(r for r in doc.rows if r.datum_address == addr)
    return str(row.raw[0][2])


class MintNodeTests(unittest.TestCase):
    def test_mint_contiguous_child(self) -> None:
        wb = _catch_all_wb()
        delta = MintNode("txa", "1-3-1", "brassica_carinata").apply(wb)
        txa = delta.touched_sheets["txa"]
        self.assertIn("1-3-1", defined_node_addrs(txa))
        self.assertEqual(len(txa.rows), len(wb.sheet("txa").rows) + 1)

    def test_mint_rejects_noncontiguous(self) -> None:
        wb = _catch_all_wb()
        with self.assertRaises(ValueError):
            MintNode("txa", "1-3-5", "x").apply(wb)  # would skip ordinals

    def test_mint_rejects_missing_parent(self) -> None:
        wb = _catch_all_wb()
        with self.assertRaises(ValueError):
            MintNode("txa", "2-9-1", "x").apply(wb)


class RelocateNodeTests(unittest.TestCase):
    def test_relocate_remaps_def_and_refs_with_sibling_shift(self) -> None:
        wb = _catch_all_wb()
        delta = RelocateNode("txa", "4-2", "1-3").apply(wb)
        self.assertEqual(delta.node_addr_remap, {"4-3": "4-2", "4-2": "1-3-1"})
        txa = delta.touched_sheets["txa"]
        product = delta.touched_sheets["product_profiles"]
        # sp_b moved under brassicaceae; sp_c shifted down into the vacated 4-2 slot
        self.assertEqual(defined_node_addrs(txa), {"1", "1-3", "4", "4-1", "4-2", "1-3-1"})
        self.assertEqual(_taxon_of(product, "4-9-2"), "1-3-1")  # was 4-2
        self.assertEqual(_taxon_of(product, "4-9-3"), "4-2")    # was 4-3 (shifted)
        self.assertEqual(_taxon_of(product, "4-9-1"), "4-1")    # untouched


class RepointAndDropTests(unittest.TestCase):
    def test_drop_blocked_while_referenced(self) -> None:
        wb = _catch_all_wb()
        with self.assertRaises(ValueError):
            DropNode("txa", "4-3").apply(wb)

    def test_repoint_then_drop(self) -> None:
        wb = _catch_all_wb()
        # fold sp_c (4-3) references onto sp_a (4-1); 4-3 def row preserved
        d1 = RepointNode("txa", "4-3", "4-1").apply(wb)
        wb1 = wb.with_sheets(d1.touched_sheets)
        self.assertEqual(_taxon_of(wb1.sheet("product_profiles"), "4-9-3"), "4-1")
        self.assertIn("4-3", defined_node_addrs(wb1.sheet("txa")))  # still defined
        # now droppable (unreferenced)
        d2 = DropNode("txa", "4-3").apply(wb1)
        txa = d2.touched_sheets["txa"]
        self.assertNotIn("4-3", defined_node_addrs(txa))
        self.assertNotIn("4-3", {str(r.raw[0][2]) for r in txa.rows if r.datum_address.startswith("4-2-")})

    def test_rewrite_refs(self) -> None:
        wb = _catch_all_wb()
        delta = RewriteRefs({"4-1": "1-3"}).apply(wb)
        product = delta.touched_sheets["product_profiles"]
        self.assertEqual(_taxon_of(product, "4-9-1"), "1-3")

    def test_rename_node(self) -> None:
        wb = _catch_all_wb()
        delta = RenameNode("txa", "4", "unspecified").apply(wb)
        txa = delta.touched_sheets["txa"]
        row = next(r for r in txa.rows if str(r.raw[0][2]) == "4")
        self.assertEqual(row.raw[1][0], "unspecified")
        self.assertEqual(row.raw[0][4], labels.encode_label_bits("unspecified"))


def _samras_wb() -> Workbook:
    node_set = {"1", "1-1", "1-2", "1-3", "1-3-1"}
    bits = samras_deps.build_magnitude_bitstream(node_set)
    txa = _doc("txa", [
        _def("4-2-1", "1", "root"),
        _def("4-2-2", "1-1", "a"),
        _def("4-2-3", "1-2", "b"),
        _def("4-2-4", "1-3", "c"),
        _def("4-2-5", "1-3-1", "c1"),
        ("5-0-1", [["5-0-1", "~", "4-2-1", "4-2-2", "4-2-3", "4-2-4", "4-2-5"], ["txa_id_collection"]]),
    ])
    anchor = _doc("anchor", [
        ("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]]),
    ])
    product = _doc("product_profiles", [_product("4-9-1", "1-3-1")])
    return Workbook(sandbox="agro_erp", sheets={"anchor": anchor, "txa": txa, "product_profiles": product})


class SamrasAndRulesTests(unittest.TestCase):
    def test_recompile_magnitude_matches_node_set(self) -> None:
        wb = _samras_wb()
        # mint a new node, then recompile 1-1-1 over the grown txa set
        wb = wb.with_sheets(MintNode("txa", "1-2-1", "b1").apply(wb).touched_sheets)
        delta = RecompileMagnitude("anchor", "1-1-1", "txa").apply(wb)
        anchor = delta.touched_sheets["anchor"]
        bits = next(r.raw[0][2] for r in anchor.rows if r.datum_address == "1-1-1")
        from MyCiteV2.packages.core.structures.samras.codec import decode_canonical_bitstream
        decoded = decode_canonical_bitstream(bits)
        self.assertEqual(len(decoded.addresses), samras_deps.closure_size(defined_node_addrs(wb.sheet("txa"))))

    def test_rebuild_collection(self) -> None:
        wb = _samras_wb()
        wb = wb.with_sheets(MintNode("txa", "1-2-1", "b1").apply(wb).touched_sheets)
        delta = RebuildCollection("txa", "5-0-1", "txa_id_collection").apply(wb)
        coll = next(r for r in delta.touched_sheets["txa"].rows if r.datum_address == "5-0-1")
        # 5 original def rows + 1 minted = 6 refs
        self.assertEqual(len(coll.raw[0]) - 2, 6)

    def test_check_step_ok(self) -> None:
        report = check_step(_samras_wb())
        self.assertTrue(report.ok, report.hard)

    def test_check_step_flags_dangling(self) -> None:
        wb = _samras_wb()
        # a product referencing a node that is defined nowhere in the sandbox
        bad_product = _doc("product_profiles", [_product("4-9-1", "8-8")])
        bad = wb.with_sheet("product_profiles", bad_product)
        report = check_step(bad)
        self.assertFalse(report.ok)
        self.assertTrue(any("dangling" in h for h in report.hard))

    def test_check_step_flags_malformed_row(self) -> None:
        bad_txa = _doc("txa", [("4-2-1", [["4-2-1", _NID]])])  # even head_len → not well_formed
        wb = Workbook(sandbox="agro_erp", sheets={"txa": bad_txa})
        report = check_step(wb)
        self.assertFalse(report.ok)
        self.assertTrue(any("malformed" in h for h in report.hard))


if __name__ == "__main__":
    unittest.main()
