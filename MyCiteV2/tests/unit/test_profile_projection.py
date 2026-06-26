"""profile_card base contract: build_profile_projection reads a vg0 collecting datum
(samras id + title + visual) and falls back to identity metadata; farm_profile composes it."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.tools.profile_projection import build_profile_projection, find_profile_datum


class _Row:
    def __init__(self, datum_address, raw):
        self.datum_address = datum_address
        self.raw = raw


class _Doc:
    def __init__(self, rows, metadata, canonical):
        self.rows = rows
        self.document_metadata = metadata
        self.canonical_name = canonical


class ProfileProjectionTests(unittest.TestCase):
    def test_metadata_fallback(self) -> None:
        doc = _Doc(rows=[], metadata={"title": "Trapp Farm", "msn_node": "3-2-3"}, canonical="farm_profile")
        p = build_profile_projection(doc)
        self.assertEqual(p["title"], "Trapp Farm")
        self.assertEqual(p["samras_node"], "3-2-3")
        self.assertEqual(p["source"], "metadata")
        self.assertFalse(p["has_visual"])

    def test_reads_vg0_collecting_datum(self) -> None:
        # value-group-0 datum: address L-0-I; head references samras (rf.3-1-1) + title (rf.3-1-2) + visual (rf.3-1-11)
        row = _Row("4-0-1", [["4-0-1", "rf.3-1-1", "1-2-3", "rf.3-1-2", "0", "rf.3-1-11", "logo.avif"], ["Greenfield"]])
        doc = _Doc(rows=[row], metadata={}, canonical="x")
        self.assertIsNotNone(find_profile_datum(doc))
        p = build_profile_projection(doc)
        self.assertEqual(p["samras_node"], "1-2-3")
        self.assertEqual(p["title"], "Greenfield")  # tail label
        self.assertEqual(p["visual_url"], "logo.avif")
        self.assertTrue(p["has_visual"])
        self.assertEqual(p["source"], "datum")

    def test_non_vg0_rows_ignored(self) -> None:
        # a layer-2 (value-group 2) row is not a profile collecting datum
        row = _Row("4-2-1", [["4-2-1", "rf.3-1-1", "9", "rf.3-1-2", "0"], ["Nope"]])
        doc = _Doc(rows=[row], metadata={"title": "Meta"}, canonical="c")
        self.assertIsNone(find_profile_datum(doc))
        self.assertEqual(build_profile_projection(doc)["title"], "Meta")


if __name__ == "__main__":
    unittest.main()
