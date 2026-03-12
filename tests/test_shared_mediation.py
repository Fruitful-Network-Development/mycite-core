from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_registry():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "mediation" / "registry.py"
    spec = importlib.util.spec_from_file_location("shared_mediation_registry_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedMediationTests(unittest.TestCase):
    def test_boolean_decode(self):
        registry = _load_registry()
        out = registry.decode_value(standard_id="boolean_ref", reference="2-1-45", magnitude="1", context={})
        self.assertTrue(out["ok"])
        self.assertTrue(out["value"])
        self.assertEqual(out["magnitude"], "1")

    def test_text_byte_email_round_trip(self):
        registry = _load_registry()
        encoded = registry.encode_value(standard_id="text_byte_email_format", value="user@example.com", context={})
        self.assertTrue(encoded["ok"])
        decoded = registry.decode_value(
            standard_id="text_byte_email_format",
            reference="",
            magnitude=encoded["magnitude"],
            context={},
        )
        self.assertTrue(decoded["ok"])
        self.assertEqual(decoded["value"], "user@example.com")

    def test_dns_wire_round_trip(self):
        registry = _load_registry()
        encoded = registry.encode_value(standard_id="dns_wire_format", value="example.com", context={})
        self.assertTrue(encoded["ok"])
        decoded = registry.decode_value(
            standard_id="dns_wire_format",
            reference="",
            magnitude=encoded["magnitude"],
            context={},
        )
        self.assertTrue(decoded["ok"])
        self.assertEqual(decoded["value"], "example.com")

    def test_timestamp_decode_display(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="timestamp_unix_s",
            reference="",
            magnitude="1700000000",
            context={},
        )
        self.assertTrue(decoded["ok"])
        self.assertEqual(decoded["value"], 1700000000)
        self.assertTrue(str(decoded["display"]).endswith("Z"))


if __name__ == "__main__":
    unittest.main()
