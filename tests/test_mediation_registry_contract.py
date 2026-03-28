from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_registry():
    path = Path(__file__).resolve().parents[1] / "portals" / "_shared" / "portal" / "mediation" / "registry.py"
    spec = importlib.util.spec_from_file_location("shared_mediation_registry_contract_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MediationRegistryContractTests(unittest.TestCase):
    def test_default_registry_entries_present(self):
        registry = _load_registry()
        entries = registry.list_registry_entries()
        by_standard = {str(item.get("standard_id") or ""): item for item in entries}
        required = {
            "boolean_ref",
            "ascii_char",
            "dns_wire_format",
            "text_byte_format",
            "timestamp_unix_s",
            "duration_s",
            "length_m",
            "coordinate",
        }
        self.assertTrue(required.issubset(set(by_standard.keys())))
        self.assertEqual(by_standard["coordinate"]["render_hint"], "coordinate_pair")

    def test_alias_resolves_to_canonical_entry(self):
        registry = _load_registry()
        entry = registry.resolve_entry("text_byte_email_format")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["standard_id"], "text_byte_format")

    def test_coordinate_fixed_hex_decode(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="coordinate_fixed_hex",
            reference="1-1-1",
            magnitude="CF69268F1894171F",
            context={},
        )
        self.assertTrue(decoded["ok"])
        value = decoded["value"]
        self.assertIsInstance(value, dict)
        self.assertIn("lat", value)
        self.assertIn("lon", value)
        self.assertEqual(value.get("encoding"), "legacy_fixed_hex")

    def test_coordinate_hops_decode(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="coordinate_hops",
            reference="",
            magnitude="3-76-10-64-12-20",
            context={},
        )
        self.assertTrue(decoded["ok"])
        value = decoded["value"]
        self.assertIsInstance(value, dict)
        self.assertEqual(value.get("encoding"), "hops_mixed_radix")

    def test_coordinate_hops_rejects_fixed_hex_without_compat_flag(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="coordinate_hops",
            reference="",
            magnitude="CF69268F1894171F",
            context={},
        )
        self.assertFalse(decoded["ok"])

    def test_coordinate_hops_malformed_value_fails(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="coordinate_hops",
            reference="",
            magnitude="bad-value",
            context={},
        )
        self.assertFalse(decoded["ok"])

    def test_coordinate_ambiguous_token_fails(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="coordinate",
            reference="",
            magnitude="CF69-268F-1894-171F",
            context={"coordinate_authority": "hops", "allow_legacy_fixed_hex": True},
        )
        self.assertFalse(decoded["ok"])

    def test_validation_errors_propagate(self):
        registry = _load_registry()
        decoded = registry.decode_value(
            standard_id="text_byte_format",
            reference="",
            magnitude="not_hex",
            context={},
        )
        self.assertFalse(decoded["ok"])
        self.assertTrue(decoded["errors"])


if __name__ == "__main__":
    unittest.main()
