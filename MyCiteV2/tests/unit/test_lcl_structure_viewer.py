"""LCL structure-tree viewer — magnitude-denoted vs lcl-defined node tree.

Sibling of test_txa_tree_viewer: the tool decodes the anchor's lcl-SAMRAS magnitude
(row 1-1-5) into the DENOTED node set, overlays which are DEFINED in the lcl doc, and
flags the rest EMPTY. Reuses ``build_magnitude_tree`` (shared with txa_tree); tests both
the pure builder against a synthetic fixture and the live agro_erp data.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops.samras_deps import build_magnitude_bitstream
from MyCiteV2.packages.ports.datum_store.contracts import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools.lcl_structure_viewer import LclStructureViewer
from MyCiteV2.packages.tools.txa_tree_viewer import build_magnitude_tree

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


def _row(addr: str, raw: list) -> AuthoritativeDatumDocumentRow:
    return AuthoritativeDatumDocumentRow(datum_address=addr, raw=raw)


def _doc(name: str, rows: list) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id=f"lv.M.agro_erp.{name}.H",
        source_kind="sandbox_source",
        document_name=name,
        relative_path="x",
        canonical_name=name,
        rows=tuple(rows),
    )


class TestLclStructurePure(unittest.TestCase):
    def test_registered_with_taxonomy_archetype(self) -> None:
        self.assertIsInstance(tools_get("lcl_structure"), LclStructureViewer)
        self.assertIn("samras_taxonomy", LclStructureViewer.applies_to_archetype)

    def _fixture(self):
        # magnitude over {1-1, 1-2, 1-3} (contiguous children of 1, per the SAMRAS
        # contiguous-ordinal rule) → prefix closure adds {1} → denoted {1,1-1,1-2,1-3}.
        bits = build_magnitude_bitstream({"1-1", "1-2", "1-3"})
        anchor = _doc("anchor", [_row("1-1-5", [["1-1-5", "0-0-5", bits], ["lcl-SAMRAS"]])])
        # lcl DEFINES {1, 1-1, 1-3}; 1-2 left undefined (denoted-but-empty).
        title = "0" * 512
        lcl = _doc("lcl", [
            _row("4-2-1", [["4-2-1", "rf.3-1-1", "1", "rf.3-1-2", title], ["root"]]),
            _row("4-2-2", [["4-2-2", "rf.3-1-1", "1-1", "rf.3-1-2", title], ["entity"]]),
            _row("4-2-3", [["4-2-3", "rf.3-1-1", "1-3", "rf.3-1-2", title], ["product"]]),
        ])
        return anchor, lcl

    def test_denoted_defined_empty(self) -> None:
        anchor, lcl = self._fixture()
        built = build_magnitude_tree(anchor, "1-1-5", lcl)
        self.assertEqual(built["denoted"], {"1", "1-1", "1-2", "1-3"})
        self.assertEqual(built["defined"], {"1", "1-1", "1-3"})
        self.assertTrue(built["defined"] <= built["denoted"])
        self.assertEqual(built["denoted"] - built["defined"], {"1-2"})

    def test_tree_hierarchy_and_status(self) -> None:
        anchor, lcl = self._fixture()
        built = build_magnitude_tree(anchor, "1-1-5", lcl)
        roots = built["tree"]
        self.assertEqual([n["address"] for n in roots], ["1"])
        kids = {n["address"]: n["status"] for n in roots[0]["children"]}
        self.assertEqual(kids, {"1-1": "defined", "1-2": "empty", "1-3": "defined"})


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLclStructureLive(unittest.TestCase):
    def test_live_agro_erp_lcl_structure(self) -> None:
        payload = LclStructureViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address=""
        )
        self.assertIsNone(payload.get("error"))
        self.assertEqual(payload["magnitude"], "lcl")
        # ≥4665 nodes (4626 base + 39 reconciled entity/role branches; grows with seed
        # docs e.g. Phase-5 equipment/livestock). The real invariant is full closure —
        # every denoted node defined (0 empty) and defined_count == denoted_count.
        self.assertGreaterEqual(payload["denoted_count"], 4665)
        self.assertEqual(payload["empty_count"], 0)
        self.assertEqual(payload["defined_count"], payload["denoted_count"])
        self.assertEqual(payload["defined_count"], payload["denoted_count"] - payload["empty_count"])
        self.assertTrue(payload["tree"], "expected a non-empty tree")


if __name__ == "__main__":
    unittest.main()
