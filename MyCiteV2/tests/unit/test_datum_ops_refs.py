"""S2 — sandbox cross-document reference index (datum_ops.refs).

Verifies marker/value detection, definition-vs-reference separation, and the
references_to / is_referenced queries on a fixture workbook. The catch-all
reference-indexing behavior is covered deterministically by
``ReferenceIndexTests`` over a fixed fixture (no live-data coupling).
"""

from __future__ import annotations

import unittest

from MyCiteV2.packages.core.datum_ops import Workbook, build_reference_index
from MyCiteV2.packages.core.datum_ops import refs as R
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)

_BLOB = "0" * 16  # a title blob: binary, >=8 bits


def _doc(name: str, rows: list[tuple[str, object]]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.3-2-3-17-77-1-6-4-1-4.agro_erp.{name}." + ("a" * 64),
        source_kind="sandbox_source",
        document_name=name,
        relative_path=f"agro_erp/{name}.json",
        rows=tuple(AuthoritativeDatumDocumentRow(datum_address=a, raw=r) for a, r in rows),
    )


def _fixture() -> Workbook:
    txa = _doc("txa", [
        ("4-2-1", [["4-2-1", "rf.3-1-1", "4", "rf.3-1-2", _BLOB], ["agro_unclassified"]]),
        ("4-2-2", [["4-2-2", "rf.3-1-1", "4-1", "rf.3-1-2", _BLOB], ["arctium_lappa"]]),
        ("4-2-3", [["4-2-3", "rf.3-1-1", "4-2", "rf.3-1-2", _BLOB], ["armoracia_rusticana"]]),
    ])
    lcl = _doc("lcl", [
        ("4-2-1", [["4-2-1", "rf.3-1-5", "1-3-1-2", "rf.3-1-2", _BLOB], ["prod_a"]]),
        ("4-2-2", [["4-2-2", "rf.3-1-5", "1-3-1-3", "rf.3-1-2", _BLOB], ["prod_b"]]),
    ])
    product = _doc("product_profiles", [
        ("4-9-1", [["4-9-1", "rf.3-1-5", "1-3-1-2", "rf.3-1-1", "4-1", "2-1-1", "8640000", "2-1-3", "18"], ["prod_a"]]),
        ("4-9-2", [["4-9-2", "rf.3-1-5", "1-3-1-3", "rf.3-1-1", "4-2", "2-1-1", "100", "2-1-3", "30"], ["prod_b"]]),
    ])
    anchor = _doc("anchor", [
        ("1-1-1", [["1-1-1", "0-0-5", "1010101010"], ["txa-SAMRAS"]]),
        ("2-1-1", [["2-1-1", "1-2-1", "0"], ["second-baciloid"]]),
    ])
    return Workbook(sandbox="agro_erp", sheets={"anchor": anchor, "txa": txa, "lcl": lcl, "product_profiles": product})


class MarkerDetectionTests(unittest.TestCase):
    def test_reference_markers(self) -> None:
        for ok in ("rf.3-1-1", "RF.3-1-5", "ref.3-1-2", "ref.4"):
            self.assertTrue(R.is_reference_marker(ok), ok)
        for bad in ("2-1-1", "0-0-5", "rfx.3-1-1", "", "4-9"):
            self.assertFalse(R.is_reference_marker(bad), bad)

    def test_node_addr_reference(self) -> None:
        for ok in ("4", "4-9", "1-3-2-5-1", "999"):
            self.assertTrue(R.is_node_addr_reference(ok), ok)
        for bad in ("0", "4-0", "8640000", _BLOB, "", "x"):
            self.assertFalse(R.is_node_addr_reference(bad), bad)

    def test_title_blob_excluded(self) -> None:
        self.assertTrue(R.is_title_blob(_BLOB))
        self.assertFalse(R.is_title_blob("4-9"))


class ReferenceIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.idx = build_reference_index(_fixture())

    def test_defined_nodes(self) -> None:
        self.assertEqual(self.idx.defined_nodes(), {"4", "4-1", "4-2", "1-3-1-2", "1-3-1-3"})
        self.assertEqual(self.idx.defining_row("4-1").sheet, "txa")
        self.assertEqual(self.idx.defining_row("1-3-1-2").sheet, "lcl")

    def test_edges_only_from_references(self) -> None:
        # Definition rows (txa/lcl) and the anchor (no rf. markers) emit no edges.
        self.assertTrue(all(e.src_sheet == "product_profiles" for e in self.idx.edges))
        # Each product row: product_id (lcl) + taxonomy (txa) = 2 node edges; the
        # 2-1-1/2-1-3 unit-abstraction pairs and title slots are NOT edges.
        self.assertEqual(len(self.idx.edges), 4)

    def test_references_to_catch_all_subtree(self) -> None:
        edges = self.idx.references_to("4")  # includes descendants 4-1, 4-2
        self.assertEqual({e.target_node_addr for e in edges}, {"4-1", "4-2"})
        self.assertEqual({e.src_row for e in edges}, {"4-9-1", "4-9-2"})
        # the rewrite slot is the magnitude index (head[4]) in both
        self.assertEqual({e.slot for e in edges}, {4})

    def test_is_referenced(self) -> None:
        self.assertTrue(self.idx.is_referenced("4-1"))
        self.assertTrue(self.idx.is_referenced("1-3-1-2"))
        # the catch-all root itself is not directly referenced (only its children are)
        self.assertFalse(any(e.target_node_addr == "4" for e in self.idx.edges))


# NOTE: LiveAgroErpIndexTests was removed — it read the deployed prod MOS DB at
# /srv/webapps/mycite/fnd/private/mos_authority.sqlite3 (skipUnless present) and
# asserted a transient magic count (102 catch-all edges pre-S7-rewrite; the live
# data has since drifted). The catch-all reference-indexing logic is covered
# deterministically by ReferenceIndexTests above over a fixed fixture.


if __name__ == "__main__":
    unittest.main()
