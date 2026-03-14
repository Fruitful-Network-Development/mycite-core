from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "portal"
        / "data_contract"
        / "anthology_save_state.py"
    )
    spec = importlib.util.spec_from_file_location("shared_anthology_save_state_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnthologySaveStateTests(unittest.TestCase):
    def test_compact_payload_to_save_state_preserves_layer_group_structure(self):
        mod = _load_module()
        payload = {
            "0-0-1": [["0-0-1", "0", "0"], ["top"]],
            "1-1-9": [["1-1-9", "0-0-1", "946707763350000000"], ["UTC_bacillete-946707763350000000"]],
            "3-1-2": [["3-1-2", "2-1-8", "0"], ["utc_babelette"]],
            "4-2-1": [["4-2-1", "1-1-9", "63072000000", "3-1-2", "1"], ["y2k-event"]],
            "4-2-2": [["4-2-2", "1-1-9", "63072000000", "3-1-2", "3153600000"], ["21st_century-event"]],
        }

        state = mod.compact_payload_to_save_state(payload)

        self.assertEqual(state["schema"], mod.SAVE_STATE_SCHEMA)
        self.assertEqual(state["encoding"], mod.SAVE_STATE_ENCODING)
        self.assertEqual(state["summary"]["layer_count"], 4)
        self.assertEqual(state["summary"]["row_count"], 5)
        self.assertEqual(state["summary"]["pair_count"], 7)
        self.assertEqual(
            state["summary"]["value_groups_per_layer"],
            [
                {"layer": 0, "count": 1},
                {"layer": 1, "count": 1},
                {"layer": 3, "count": 1},
                {"layer": 4, "count": 1},
            ],
        )
        self.assertEqual(
            state["summary"]["iterations_per_group"],
            [
                {"layer": 0, "value_group": 0, "count": 1},
                {"layer": 1, "value_group": 1, "count": 1},
                {"layer": 3, "value_group": 1, "count": 1},
                {"layer": 4, "value_group": 2, "count": 2},
            ],
        )
        vg2_rows = state["layers"][3]["value_groups"][0]["rows"]
        self.assertEqual(vg2_rows[0]["identifier"], "4-2-1")
        self.assertEqual(
            vg2_rows[0]["pairs"],
            [["1-1-9", "63072000000"], ["3-1-2", "1"]],
        )

    def test_save_state_round_trips_compact_payload(self):
        mod = _load_module()
        payload = {
            "0-0-1": [["0-0-1", "0", "0"], ["top"]],
            "4-0-1": [["4-0-1", "3-2-2", "3-2-2,3-2-3", "3-2-3", "0"], ["time-series-anchor"]],
            "4-2-1": [["4-2-1", "3-2-2", "1735689600", "3-2-3", "31536000"], ["2025-event"]],
            "1-1-1": [["1-1-1", "0-0-4", "16162550000000000000000000000000000000"], ["centameter"]],
        }

        state = mod.compact_payload_to_save_state(payload)
        rebuilt = mod.save_state_to_compact_payload(state)

        self.assertEqual(rebuilt, payload)

    def test_rows_to_save_state_rejects_pair_count_mismatch(self):
        mod = _load_module()
        rows = [
            {
                "row_id": "4-2-1",
                "identifier": "4-2-1",
                "label": "broken-event",
                "pairs": [{"reference": "1-1-9", "magnitude": "63072000000"}],
                "reference": "1-1-9",
                "magnitude": "63072000000",
            }
        ]

        with self.assertRaises(ValueError):
            mod.rows_to_save_state(rows)


if __name__ == "__main__":
    unittest.main()
