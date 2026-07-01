"""Unified SAMRAS structure viewer — discovery, selection, and the shared tree builder.

Replaces test_txa_tree_viewer + test_lcl_structure_viewer. The one tool discovers the
anchor's ``*-SAMRAS`` node structures (txa / msn / lcl), renders the one chosen via
``surface_query["samras_structure"]`` through the shared ``build_magnitude_tree``, and
degrades gracefully for a structure with no definition doc (msn → blank labels). Tests the
pure builder + discovery (synthetic), the selection logic (monkeypatched store), and the
live agro_erp data.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.core.datum_ops.samras_deps import build_magnitude_bitstream
from MyCiteV2.packages.ports.datum_store.contracts import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools import samras_structure_viewer as ssv
from MyCiteV2.packages.tools.samras_structure_viewer import (
    SamrasStructureViewer,
    build_magnitude_tree,
    discover_samras_structures,
)

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")
_TITLE = "0" * 512


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


def _def_row(addr: str, node: str, label: str) -> AuthoritativeDatumDocumentRow:
    return _row(addr, [[addr, "rf.3-1-1", node, "rf.3-1-2", _TITLE], [label]])


class TestRegistration(unittest.TestCase):
    def test_registered_with_taxonomy_archetype(self) -> None:
        self.assertIsInstance(tools_get("samras_structure"), SamrasStructureViewer)
        self.assertIn("samras_taxonomy", SamrasStructureViewer.applies_to_archetype)
        self.assertTrue(getattr(SamrasStructureViewer, "wants_surface_query", False))
        # the retired per-structure tools are gone from the registry
        self.assertIsNone(tools_get("txa_tree"))
        self.assertIsNone(tools_get("lcl_structure"))


class TestBuildMagnitudeTree(unittest.TestCase):
    def _txa_fixture(self):
        bits = build_magnitude_bitstream({"1-1", "1-2"})
        anchor = _doc("anchor", [_row("1-1-1", [["1-1-1", "0-0-5", bits], ["txa-SAMRAS"]])])
        txa = _doc("txa", [_def_row("4-2-1", "1", "root"), _def_row("4-2-2", "1-2", "branch_two")])
        return anchor, txa

    def test_txa_denoted_defined_empty(self) -> None:
        anchor, txa = self._txa_fixture()
        built = build_magnitude_tree(anchor, "1-1-1", txa)
        self.assertEqual(built["denoted"], {"1", "1-1", "1-2"})
        self.assertEqual(built["defined"], {"1", "1-2"})
        self.assertTrue(built["defined"] <= built["denoted"])
        self.assertEqual(built["denoted"] - built["defined"], {"1-1"})

    def test_flat_nodes_shape_and_status(self) -> None:
        anchor, txa = self._txa_fixture()
        built = build_magnitude_tree(anchor, "1-1-1", txa)
        nodes = {n["full_slug"]: n for n in built["nodes"]}
        # cluster-dendrogram shape: full_slug / parent_slug / depth / has_children + status
        self.assertEqual(set(nodes), {"1", "1-1", "1-2"})
        self.assertEqual(nodes["1"]["parent_slug"], "")
        self.assertEqual(nodes["1"]["depth"], 0)
        self.assertTrue(nodes["1"]["has_children"])
        self.assertEqual(nodes["1"]["status"], "defined")
        # direct child count drives the node's pill badge (Resource-style chip)
        self.assertEqual(nodes["1"]["count"], 2)
        self.assertEqual(nodes["1-1"]["parent_slug"], "1")
        self.assertEqual(nodes["1-1"]["depth"], 1)
        self.assertFalse(nodes["1-1"]["has_children"])
        self.assertEqual(nodes["1-1"]["status"], "empty")
        self.assertEqual(nodes["1-1"]["count"], 0)
        self.assertEqual(nodes["1-2"]["status"], "defined")
        self.assertEqual(nodes["1-2"]["count"], 0)

    def test_lcl_fixture(self) -> None:
        bits = build_magnitude_bitstream({"1-1", "1-2", "1-3"})
        anchor = _doc("anchor", [_row("1-1-5", [["1-1-5", "0-0-5", bits], ["lcl-SAMRAS"]])])
        lcl = _doc("lcl", [
            _def_row("4-2-1", "1", "root"),
            _def_row("4-2-2", "1-1", "entity"),
            _def_row("4-2-3", "1-3", "product"),
        ])
        built = build_magnitude_tree(anchor, "1-1-5", lcl)
        self.assertEqual(built["denoted"], {"1", "1-1", "1-2", "1-3"})
        self.assertEqual(built["denoted"] - built["defined"], {"1-2"})

    def test_no_defining_doc_blank_labels(self) -> None:
        bits = build_magnitude_bitstream({"1-1"})
        anchor = _doc("anchor", [_row("1-1-4", [["1-1-4", "0-0-5", bits], ["msn-SAMRAS"]])])
        built = build_magnitude_tree(anchor, "1-1-4", None)
        self.assertEqual(built["defined"], set())
        self.assertTrue(built["nodes"])
        self.assertTrue(all(n["label"] == "" for n in built["nodes"]))
        self.assertTrue(all(n["status"] == "empty" for n in built["nodes"]))

    def test_missing_magnitude_returns_none(self) -> None:
        anchor = _doc("anchor", [_row("9-9-9", [["9-9-9", "x"], ["other"]])])
        self.assertIsNone(build_magnitude_tree(anchor, "1-1-1", None))


class TestDiscovery(unittest.TestCase):
    def _multi_anchor(self):
        return _doc("anchor", [
            _row("1-1-1", [["1-1-1", "0-0-5", build_magnitude_bitstream({"1-1", "1-2"})], ["txa-SAMRAS"]]),
            # HOPS magnitude — must be EXCLUDED (label does not end in -SAMRAS)
            _row("1-1-3", [["1-1-3", "0-0-5", "0101"], ["HOPS-spacial"]]),
            _row("1-1-4", [["1-1-4", "0-0-5", build_magnitude_bitstream({"1"})], ["msn-SAMRAS"]]),
            _row("1-1-5", [["1-1-5", "0-0-5", build_magnitude_bitstream({"1-1", "1-2", "1-3"})], ["lcl-SAMRAS"]]),
        ])

    def test_discovers_samras_excludes_hops_in_address_order(self) -> None:
        found = discover_samras_structures(self._multi_anchor())
        self.assertEqual([s["name"] for s in found], ["txa", "msn", "lcl"])
        self.assertEqual([s["magnitude_addr"] for s in found], ["1-1-1", "1-1-4", "1-1-5"])


class TestSelection(unittest.TestCase):
    """build_panel_payload structure selection, with the store monkeypatched."""

    def _setup(self):
        anchor = _doc("anchor", [
            _row("1-1-1", [["1-1-1", "0-0-5", build_magnitude_bitstream({"1-1", "1-2"})], ["txa-SAMRAS"]]),
            _row("1-1-4", [["1-1-4", "0-0-5", build_magnitude_bitstream({"1"})], ["msn-SAMRAS"]]),
            _row("1-1-5", [["1-1-5", "0-0-5", build_magnitude_bitstream({"1-1", "1-2", "1-3"})], ["lcl-SAMRAS"]]),
        ])
        txa = _doc("txa", [_def_row("4-2-1", "1", "root"), _def_row("4-2-2", "1-2", "two")])
        lcl = _doc("lcl", [_def_row("4-2-1", "1", "root"), _def_row("4-2-2", "1-1", "entity"),
                           _def_row("4-2-3", "1-3", "product")])
        docs = [anchor, txa, lcl]  # NOTE: no "msn" doc on purpose

        def fake_find(docs_, *, sandbox, name):
            return next((d for d in docs_ if d.canonical_name == name), None)

        return docs, fake_find

    def _payload(self, extra_query):
        docs, fake_find = self._setup()
        with mock.patch.object(ssv, "read_sandbox_catalog", return_value=(docs, "")), \
                mock.patch.object(ssv, "find_named_document", side_effect=fake_find):
            return SamrasStructureViewer().build_panel_payload(
                authority_db_file=Path("x"), sandbox_id="agro_erp",
                document_id="", datum_address="", extra_query=extra_query,
            )

    def test_default_is_first_by_address(self) -> None:
        p = self._payload(None)
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["structure"], "txa")
        self.assertEqual([s["name"] for s in p["structures"]], ["txa", "msn", "lcl"])
        self.assertEqual({s["name"]: s["has_titles"] for s in p["structures"]},
                         {"txa": True, "msn": False, "lcl": True})

    def test_select_lcl(self) -> None:
        p = self._payload({"samras_structure": "lcl"})
        self.assertEqual(p["structure"], "lcl")
        self.assertTrue(p["has_titles"])
        self.assertEqual(p["denoted_count"], 4)  # {1,1-1,1-2,1-3}

    def test_select_msn_no_titles(self) -> None:
        p = self._payload({"samras_structure": "msn"})
        self.assertEqual(p["structure"], "msn")
        self.assertFalse(p["has_titles"])
        self.assertTrue(p["nodes"])

    def test_unknown_selection_falls_back_to_first(self) -> None:
        p = self._payload({"samras_structure": "nope"})
        self.assertEqual(p["structure"], "txa")


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLive(unittest.TestCase):
    def _live(self, structure):
        return SamrasStructureViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="",
            datum_address="", extra_query={"samras_structure": structure},
        )

    def test_live_txa(self) -> None:
        # Robust bounds rather than exact counts (the live taxonomy grows over time).
        p = self._live("txa")
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["structure"], "txa")
        self.assertGreater(p["denoted_count"], 0)
        self.assertTrue(p["nodes"])

    def test_live_lcl_full_closure(self) -> None:
        # The lcl id-space is large and re-authored by the restructure migration; assert a
        # robust lower bound + the defined==denoted closure invariant, not an exact count.
        p = self._live("lcl")
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["structure"], "lcl")
        self.assertGreaterEqual(p["denoted_count"], 2000)
        self.assertEqual(p["empty_count"], 0)
        self.assertEqual(p["defined_count"], p["denoted_count"])

    def test_live_msn_structure_only(self) -> None:
        p = self._live("msn")
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["structure"], "msn")
        self.assertFalse(p["has_titles"])  # no msn definition doc
        self.assertGreater(p["denoted_count"], 0)

    def test_live_structures_listed(self) -> None:
        names = [s["name"] for s in self._live("txa")["structures"]]
        self.assertEqual(names, ["txa", "msn", "lcl"])


if __name__ == "__main__":
    unittest.main()
