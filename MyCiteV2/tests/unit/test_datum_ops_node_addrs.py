"""S1 — node-address algebra + row-op wrappers (datum_ops).

Verifies the variable-depth node-address algebra (parent/child, contiguous
allocation, re-parent remap with descendant ride-along) and that the row-level
ops are faithful thin wrappers over datum_semantics.preview_document_*.
"""

from __future__ import annotations

import unittest

from MyCiteV2.packages.adapters.sql.datum_semantics import (
    preview_document_delete,
    preview_document_insert,
    preview_document_move,
)
from MyCiteV2.packages.core.datum_ops import (
    DeleteRow,
    InsertRow,
    MoveRow,
    ReorderRow,
    Workbook,
    apply_sequence,
)
from MyCiteV2.packages.core.datum_ops import node_addrs as na
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)


def _doc(rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="lv.3-2-3-17-77-1-6-4-1-4.agro_erp.txa." + ("a" * 64),
        source_kind="sandbox_source",
        document_name="txa",
        relative_path="agro_erp/txa.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _txa_doc() -> AuthoritativeDatumDocument:
    # A small txa-shaped family of 4-2-N rows carrying node_addr values.
    return _doc([
        ("4-2-1", [["4-2-1", "rf.3-1-1", "4", "rf.3-1-2", "x"], ["root"]]),
        ("4-2-2", [["4-2-2", "rf.3-1-1", "4-1", "rf.3-1-2", "x"], ["a"]]),
        ("4-2-3", [["4-2-3", "rf.3-1-1", "4-2", "rf.3-1-2", "x"], ["b"]]),
        ("4-2-4", [["4-2-4", "rf.3-1-1", "1-3", "rf.3-1-2", "x"], ["genus"]]),
    ])


class NodeAddrAlgebraTests(unittest.TestCase):
    def test_is_node_addr(self) -> None:
        for ok in ("4", "4-9", "1-3-2-5-1", "10-200"):
            self.assertTrue(na.is_node_addr(ok), ok)
        for bad in ("", "4-", "4-0", "-1", "abc", "4-x"):
            self.assertFalse(na.is_node_addr(bad), bad)

    def test_parent_and_depth(self) -> None:
        self.assertEqual(na.parent_of("4-9-1"), "4-9")
        self.assertEqual(na.parent_of("4"), "")
        self.assertEqual(na.depth("1-3-2-5-1"), 5)

    def test_is_descendant(self) -> None:
        self.assertTrue(na.is_descendant("4-9-1", "4-9"))
        self.assertTrue(na.is_descendant("4-9-1-2", "4-9"))
        self.assertFalse(na.is_descendant("4-9", "4-9"))  # self is not a descendant
        self.assertFalse(na.is_descendant("4-90", "4-9"))  # prefix-string, not tree-child

    def test_child_ordinals_and_contiguity(self) -> None:
        nodes = {"1-3", "1-3-1", "1-3-2", "1-3-3"}
        self.assertEqual(na.child_ordinals("1-3", nodes), [1, 2, 3])
        self.assertTrue(na.child_ordinals_contiguous("1-3", nodes))
        self.assertEqual(na.next_child_ordinal("1-3", nodes), 4)
        self.assertEqual(na.next_child("1-3", nodes), "1-3-4")
        # a gap breaks contiguity
        self.assertFalse(na.child_ordinals_contiguous("1-3", {"1-3", "1-3-1", "1-3-3"}))

    def test_next_child_on_empty_parent_starts_at_1(self) -> None:
        self.assertEqual(na.next_child("1-3-2-5", {"1-3-2-5"}), "1-3-2-5-1")
        self.assertEqual(na.next_child("", {"1", "2", "3"}), "4")  # root level

    def test_relocate_subtree_remap_rides_descendants(self) -> None:
        # relocate_subtree_remap is the contiguity-preserving move (removal renumber
        # + append under new parent); descendants ride along.
        nodes = {"1-3", "4", "4-9", "4-9-1", "4-9-2", "4-9-1-1"}
        remap, new_node = na.relocate_subtree_remap("4-9", "1-3", nodes)
        self.assertEqual(new_node, "1-3-1")
        self.assertEqual(remap["4-9"], "1-3-1")
        self.assertEqual(remap["4-9-1"], "1-3-1-1")
        self.assertEqual(remap["4-9-1-1"], "1-3-1-1-1")


class RowOpWrapperTests(unittest.TestCase):
    def test_insert_matches_engine(self) -> None:
        doc = _txa_doc()
        wb = Workbook(sandbox="agro_erp", sheets={"txa": doc})
        raw = [["4-2-2", "rf.3-1-1", "9-9", "rf.3-1-2", "x"], ["new"]]
        delta = InsertRow("txa", "4-2-2", raw).apply(wb)
        engine = preview_document_insert(doc, target_address="4-2-2", raw=raw)
        self.assertEqual(
            [(r.datum_address, r.raw) for r in delta.touched_sheets["txa"].rows],
            [(r.datum_address, r.raw) for r in engine["updated_document"].rows],
        )
        self.assertEqual(delta.address_map, engine["address_map"])

    def test_delete_matches_engine(self) -> None:
        doc = _txa_doc()
        wb = Workbook(sandbox="agro_erp", sheets={"txa": doc})
        delta = DeleteRow("txa", "4-2-2").apply(wb)
        engine = preview_document_delete(doc, target_address="4-2-2")
        self.assertEqual(
            [r.datum_address for r in delta.touched_sheets["txa"].rows],
            [r.datum_address for r in engine["updated_document"].rows],
        )

    def test_move_matches_engine(self) -> None:
        doc = _txa_doc()
        wb = Workbook(sandbox="agro_erp", sheets={"txa": doc})
        delta = MoveRow("txa", "4-2-4", "4-2-1").apply(wb)
        engine = preview_document_move(doc, source_address="4-2-4", destination_address="4-2-1")
        self.assertEqual(delta.address_map, engine["address_map"])

    def test_apply_sequence_threads_deltas(self) -> None:
        doc = _txa_doc()
        wb = Workbook(sandbox="agro_erp", sheets={"txa": doc})
        raw = [["4-2-5", "rf.3-1-1", "9-9", "rf.3-1-2", "x"], ["new"]]
        final, deltas = apply_sequence(wb, [InsertRow("txa", "4-2-5", raw), DeleteRow("txa", "4-2-1")])
        self.assertEqual(len(deltas), 2)
        # net: started with 4, +1 insert, -1 delete = 4 rows
        self.assertEqual(len(final.sheet("txa").rows), 4)

    def test_reorder_rejects_cross_family(self) -> None:
        doc = _txa_doc()
        wb = Workbook(sandbox="agro_erp", sheets={"txa": doc})
        with self.assertRaises(ValueError):
            ReorderRow("txa", "4-2-1", "5-0-1").apply(wb)


if __name__ == "__main__":
    unittest.main()
