"""TXA structure-tree viewer — magnitude-denoted vs txa-defined node tree.

The tool decodes the anchor's txa-SAMRAS magnitude (row 1-1-1) into the full set of
DENOTED node addresses, overlays which are DEFINED in the txa doc, and renders the rest
as EMPTY placeholders. Reuses the SAMRAS codec + datum_ops; tests both the pure builder
(synthetic fixture) and the live agro_erp data.
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
from MyCiteV2.packages.tools.txa_tree_viewer import TxaTreeViewer, build_magnitude_tree

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


class TestTxaTreePure(unittest.TestCase):
    def test_registered_with_taxonomy_archetype(self) -> None:
        self.assertIsInstance(tools_get("txa_tree"), TxaTreeViewer)
        self.assertIn("mycite.v2.datum.agro_erp.taxonomy_source.v1", TxaTreeViewer.applies_to_archetype)

    def _fixture(self):
        # magnitude over {1-1, 1-2} → prefix closure adds {1} → denoted {1, 1-1, 1-2}.
        bits = build_magnitude_bitstream({"1-1", "1-2"})
        anchor = _doc("anchor", [_row("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]])])
        # txa DEFINES {1, 1-2} (5-elem id-pair + title-blob heads); 1-1 left undefined.
        title = "0" * 512
        txa = _doc("txa", [
            _row("4-2-1", [["4-2-1", "rf.3-1-1", "1", "rf.3-1-2", title], ["root"]]),
            _row("4-2-2", [["4-2-2", "rf.3-1-1", "1-2", "rf.3-1-2", title], ["branch_two"]]),
        ])
        return anchor, txa

    def test_denoted_defined_empty(self) -> None:
        anchor, txa = self._fixture()
        built = build_magnitude_tree(anchor, "1-1-1", txa)
        self.assertEqual(built["denoted"], {"1", "1-1", "1-2"})
        self.assertEqual(built["defined"], {"1", "1-2"})
        self.assertTrue(built["defined"] <= built["denoted"])
        self.assertEqual(built["denoted"] - built["defined"], {"1-1"})

    def test_tree_hierarchy_and_status(self) -> None:
        anchor, txa = self._fixture()
        built = build_magnitude_tree(anchor, "1-1-1", txa)
        roots = built["tree"]
        self.assertEqual([n["address"] for n in roots], ["1"])
        root = roots[0]
        self.assertEqual(root["status"], "defined")
        # children extend the parent address; 1-1 is empty, 1-2 is defined.
        kids = {n["address"]: n["status"] for n in root["children"]}
        self.assertEqual(kids, {"1-1": "empty", "1-2": "defined"})
        for child in root["children"]:
            self.assertTrue(child["address"].startswith(root["address"] + "-"))

    def test_missing_magnitude_returns_none(self) -> None:
        anchor = _doc("anchor", [_row("9-9-9", [["9-9-9", "x"], ["other"]])])
        self.assertIsNone(build_magnitude_tree(anchor, "1-1-1", None))


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestTxaTreeLive(unittest.TestCase):
    def test_live_agro_erp_txa_tree(self) -> None:
        payload = TxaTreeViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address=""
        )
        self.assertIsNone(payload.get("error"))
        self.assertEqual(payload["magnitude"], "txa")
        self.assertEqual(payload["denoted_count"], 1038)
        self.assertEqual(payload["empty_count"], 1)
        self.assertEqual(payload["defined_count"], payload["denoted_count"] - payload["empty_count"])
        self.assertTrue(payload["tree"], "expected a non-empty tree")


if __name__ == "__main__":
    unittest.main()
