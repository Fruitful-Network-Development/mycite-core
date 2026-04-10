from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


def _load_module():
    portals_root = Path(__file__).resolve().parents[1] / "instances"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.coordinate_hops")


class CoordinateHopsTests(unittest.TestCase):
    def test_decode_hops_address(self):
        mod = _load_module()
        out = mod.decode_coordinate_token("3-76-10-64-12-20")
        self.assertIsInstance(out, dict)
        self.assertEqual(out.get("encoding"), "hops_mixed_radix")
        self.assertIn("longitude", out)
        self.assertIn("latitude", out)

    def test_decode_fixed_hex_fallback(self):
        mod = _load_module()
        out = mod.decode_coordinate_token("CF69268F1894171F", authority="hops", allow_legacy_fixed_hex=True)
        self.assertIsInstance(out, dict)
        self.assertEqual(out.get("encoding"), "legacy_fixed_hex")
        self.assertIn("normalized_hex", out)

    def test_rejects_fixed_hex_when_hops_authority_is_strict(self):
        mod = _load_module()
        out = mod.decode_coordinate_token("CF69268F1894171F", authority="hops", allow_legacy_fixed_hex=False)
        self.assertIsNone(out)

    def test_out_of_schema_hops_address_rejected(self):
        mod = _load_module()
        out = mod.decode_coordinate_token("9-1-1", authority="hops")
        self.assertIsNone(out)

    def test_malformed_coordinate_rejected(self):
        mod = _load_module()
        out = mod.decode_coordinate_token("not-a-coordinate", authority="auto", allow_legacy_fixed_hex=True)
        self.assertIsNone(out)

    def test_ambiguous_hyphenated_hex_is_classified_ambiguous(self):
        mod = _load_module()
        cls = mod.classify_coordinate_token("CF69-268F-1894-171F")
        self.assertEqual(cls.get("classification"), "ambiguous")
        decoded = mod.decode_coordinate_token("CF69-268F-1894-171F", authority="auto", allow_legacy_fixed_hex=True)
        self.assertIsNone(decoded)


if __name__ == "__main__":
    unittest.main()
