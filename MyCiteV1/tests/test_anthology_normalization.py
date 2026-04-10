from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "instances"
        / "_shared"
        / "portal"
        / "data_engine"
        / "anthology_normalization.py"
    )
    spec = importlib.util.spec_from_file_location("shared_anthology_normalization_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnthologyNormalizationTests(unittest.TestCase):
    def test_sort_rows_layer_value_group_iteration(self):
        mod = _load_module()
        rows = [
            {"identifier": "3-2-10"},
            {"identifier": "1-2-3"},
            {"identifier": "1-1-9"},
            {"identifier": "1-1-1"},
            {"identifier": "2-9-4"},
        ]
        sorted_rows = mod.sort_rows(rows)
        self.assertEqual(
            [item["identifier"] for item in sorted_rows],
            ["1-1-1", "1-1-9", "1-2-3", "2-9-4", "3-2-10"],
        )

    def test_compact_iterations_remaps_identifiers(self):
        mod = _load_module()
        rows = [
            {"row_id": "4-0-2", "identifier": "4-0-2", "reference": "3-1-13", "magnitude": "0"},
            {"row_id": "4-0-4", "identifier": "4-0-4", "reference": "3-1-827", "magnitude": "0"},
            {"row_id": "4-1-7", "identifier": "4-1-7", "reference": "4-0-2", "magnitude": "1"},
        ]
        result = mod.compact_iterations(rows)
        self.assertTrue(result.changed)
        self.assertEqual(result.identifier_map["4-0-2"], "4-0-1")
        self.assertEqual(result.identifier_map["4-0-4"], "4-0-2")
        self.assertEqual(result.identifier_map["4-1-7"], "4-1-1")
        self.assertEqual(
            [item["identifier"] for item in result.rows],
            ["4-0-1", "4-0-2", "4-1-1"],
        )

    def test_parse_invalid_identifier(self):
        mod = _load_module()
        self.assertEqual(mod.parse_datum_identifier("not-a-datum"), (None, None, None))


if __name__ == "__main__":
    unittest.main()
