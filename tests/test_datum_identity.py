"""
Tests for datum identity: semantic equivalence and compiled index by canonical path.

Verifies that two datums with the same canonical path are treated as identical
regardless of storage order or local row position, and that the compiled index
is keyed by canonical path.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTALS_ROOT = REPO_ROOT / "portals"
SHARED_ROOT = PORTALS_ROOT / "_shared"


def _load_datum_identity():
    if str(SHARED_ROOT) not in sys.path:
        sys.path.insert(0, str(SHARED_ROOT))
    import portal.data_engine.datum_identity as mod
    return mod


class DatumIdentityTests(unittest.TestCase):
    def test_datum_paths_equivalent_same_canonical(self):
        mod = _load_datum_identity()
        msn = "3-2-3-17-77-1-6-4-1-4"
        self.assertTrue(
            mod.datum_paths_equivalent("4-2-1", f"{msn}.4-2-1", local_msn_id=msn)
        )
        self.assertTrue(
            mod.datum_paths_equivalent(f"{msn}.4-2-1", "4-2-1", local_msn_id=msn)
        )

    def test_datum_paths_equivalent_different_address_not_equivalent(self):
        mod = _load_datum_identity()
        msn = "3-2-3-17-77-1-6-4-1-4"
        self.assertFalse(
            mod.datum_paths_equivalent("4-2-1", "4-2-2", local_msn_id=msn)
        )

    def test_compile_compact_array_entries_keyed_by_path(self):
        mod = _load_datum_identity()
        source_msn = "3-2-3-17-77-1-6-4-1-4"
        rows = [
            {"identifier": "4-2-2", "row_id": "4-2-2", "label": "event-b"},
            {"identifier": "4-2-1", "row_id": "4-2-1", "label": "event-a"},
        ]
        entries = mod.compile_compact_array_entries_keyed_by_path(
            rows, source_msn_id=source_msn
        )
        self.assertIn(f"{source_msn}.4-2-1", entries)
        self.assertIn(f"{source_msn}.4-2-2", entries)
        self.assertEqual(entries[f"{source_msn}.4-2-1"]["storage_address"], "4-2-1")
        self.assertEqual(entries[f"{source_msn}.4-2-1"]["label"], "event-a")
        self.assertEqual(entries[f"{source_msn}.4-2-2"]["label"], "event-b")

    def test_compiled_index_same_path_different_row_order(self):
        """Same semantic datums in different row order produce same canonical keys."""
        mod = _load_datum_identity()
        source_msn = "3-2-3-17-77-1-6-4-1-4"
        rows_a = [
            {"identifier": "4-2-1", "row_id": "4-2-1", "label": "y2k"},
            {"identifier": "4-2-2", "row_id": "4-2-2", "label": "21st"},
        ]
        rows_b = [
            {"identifier": "4-2-2", "row_id": "4-2-2", "label": "21st"},
            {"identifier": "4-2-1", "row_id": "4-2-1", "label": "y2k"},
        ]
        entries_a = mod.compile_compact_array_entries_keyed_by_path(
            rows_a, source_msn_id=source_msn
        )
        entries_b = mod.compile_compact_array_entries_keyed_by_path(
            rows_b, source_msn_id=source_msn
        )
        self.assertEqual(set(entries_a.keys()), set(entries_b.keys()))
        for path in entries_a:
            self.assertEqual(entries_a[path]["datum_path"], entries_b[path]["datum_path"])
            self.assertEqual(entries_a[path]["storage_address"], entries_b[path]["storage_address"])


if __name__ == "__main__":
    unittest.main()
