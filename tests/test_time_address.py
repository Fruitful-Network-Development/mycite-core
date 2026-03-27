from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


def _load_time_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.time_address")


class TimeAddressTests(unittest.TestCase):
    def test_compare_is_numeric_not_lexicographic(self):
        mod = _load_time_module()
        self.assertLess(
            mod.compare_time_addresses("13-787-2026-3-58", "13-787-2026-3-589"),
            0,
        )

    def test_normalize_range_repairs_mixed_specificity_when_allowed(self):
        mod = _load_time_module()
        start, end = mod.normalize_range(
            "13-787-2026-3-26",
            "13-787-2026-3-27-8-7",
            allow_repair=True,
        )
        self.assertEqual(start, "13-787-2026-3-26-0-0")
        self.assertEqual(end, "13-787-2026-3-27-8-7")

    def test_normalize_range_rejects_mixed_specificity_without_repair(self):
        mod = _load_time_module()
        with self.assertRaises(ValueError):
            mod.normalize_range(
                "13-787-2026-3-26",
                "13-787-2026-3-27-8-7",
                allow_repair=False,
            )

    def test_contains_address_scope(self):
        mod = _load_time_module()
        self.assertTrue(mod.contains_address("13-787-2026-3", "13-787-2026-3-26-7-2"))
        self.assertFalse(mod.contains_address("13-787-2026-4", "13-787-2026-3-26"))

    def test_same_scope_intersection(self):
        mod = _load_time_module()
        selected = "13-787-2026-3"
        obj_range = ["13-787-2026-3-26", "13-787-2026-3-26"]
        self.assertTrue(mod.same_scope(selected, obj_range))
        self.assertFalse(mod.same_scope("13-787-2027-3", obj_range))


if __name__ == "__main__":
    unittest.main()
