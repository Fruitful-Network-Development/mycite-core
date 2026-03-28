from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


def _load_schema_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.application.time_address_schema")


class TimeAddressSchemaTests(unittest.TestCase):
    def test_decode_known_magnitude(self):
        mod = _load_schema_module()
        bits = "00000010001110000100001110011000100001100111111011111010001111101000101101101111100111100"
        decoded = mod.decode_mixed_radix_magnitude(bits)
        self.assertEqual(list(decoded.denotations), [14, 1000, 1000, 365, 60, 60])

    def test_schema_from_anchor_payload_reads_1_1_1(self):
        mod = _load_schema_module()
        payload = {
            "1-1-1": [
                ["1-1-1", "0-0-1", "00000010001110000100001110011000100001100111111011111010001111101000101101101111100111100"],
                ["UTC_mixed_radix"],
            ]
        }
        out = mod.schema_from_anchor_payload(payload)
        self.assertTrue(bool(out.get("ok")))
        schema = out.get("schema") if isinstance(out.get("schema"), dict) else {}
        self.assertEqual(schema.get("datum_id"), "1-1-1")
        self.assertEqual(schema.get("label"), "UTC_mixed_radix")
        self.assertEqual(schema.get("denotation_count"), 6)

    def test_validate_address_full_mode(self):
        mod = _load_schema_module()
        schema_payload = {
            "ok": True,
            "schema": {
                "denotations": [14, 1000, 1000, 365, 60, 60],
                "validation_mode": "full",
            },
        }
        valid = mod.validate_address_with_schema("13-787-26-3-26", schema_payload)
        self.assertTrue(bool(valid.get("ok")))
        invalid = mod.validate_address_with_schema("15-787-26-3-26", schema_payload)
        self.assertFalse(bool(invalid.get("ok")))

    def test_validate_address_fails_when_schema_unavailable(self):
        mod = _load_schema_module()
        out = mod.validate_address_with_schema("13-787-26", {"ok": False, "error": "missing 1-1-1"})
        self.assertFalse(bool(out.get("ok")))
        self.assertIn("missing 1-1-1", str(out.get("error") or ""))


if __name__ == "__main__":
    unittest.main()
