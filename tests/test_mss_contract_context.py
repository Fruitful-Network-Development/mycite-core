from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path


REMOTE_MSN_ID = "3-2-3-17-77-2-6-3-1-6"


def _load_shared_mss():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.mss")


def _example_payload() -> dict[str, object]:
    return {
        "0-0-1": [["0-0-1", "0", "0"], ["top"]],
        "0-0-2": [["0-0-2", "0", "0"], ["tiu"]],
        "1-1-1": [["1-1-1", "0-0-2", "315569254450000000000000000000000000000"], ["sec-babel"]],
        "1-1-2": [["1-1-2", "0-0-1", "946707763350000000"], ["utc-bacillete"]],
        "2-1-1": [["2-1-1", "1-1-2", "1"], ["second-isolette"]],
        "3-1-1": [["3-1-1", "2-1-1", "0"], ["utc-babelette"]],
        "4-2-1": [["4-2-1", "1-1-1", "63072000000", "3-1-1", "1"], ["y2k-event"]],
        "4-2-2": [["4-2-2", "1-1-1", "63072000000", "3-1-1", "3153600000"], ["21st_century-event"]],
    }


def _reference_fixture_contract() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parents[1]
        / "mss"
        / "msn-3-2-3-17-77-1-6-4-1-4.contract-3-2-3-17-77-2-6-3-1-6.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


class MssContractContextTests(unittest.TestCase):
    def test_compile_decode_and_root_selection_round_trip(self):
        mod = _load_shared_mss()
        compiled = mod.compile_mss_payload(_example_payload(), ["4-2-1", "4-2-2"])

        self.assertTrue(compiled["bitstring"])
        self.assertEqual(compiled["wire_variant"], "canonical")
        self.assertEqual(compiled["root_identifier"], "5-0-1")
        self.assertEqual(compiled["selected_compact_refs"], ["4-2-1", "4-2-2"])
        self.assertEqual(len(compiled["cobm"]), 5)
        self.assertEqual(compiled["cobm"][-1]["active_identifiers"], ["4-2-1", "4-2-2"])

        decoded = mod.decode_mss_payload(compiled["bitstring"])
        self.assertEqual(decoded["wire_variant"], "canonical")
        row_ids = [row["identifier"] for row in decoded["rows"]]
        self.assertIn("5-0-1", row_ids)
        root_row = next(row for row in decoded["rows"] if row["identifier"] == "5-0-1")
        self.assertEqual([pair["reference"] for pair in root_row["pairs"]], ["4-2-1", "4-2-2"])
        self.assertEqual(decoded["metadata"]["layer_count"], 6)

    def test_reference_fixture_decodes_with_legacy_variant(self):
        mod = _load_shared_mss()
        fixture = _reference_fixture_contract()
        decoded = mod.decode_mss_payload(str(fixture.get("owner_mss") or ""))

        self.assertEqual(decoded["wire_variant"], "legacy_reference_fixture")
        self.assertFalse(decoded["legacy_unsupported"])
        self.assertEqual(decoded["root_identifier"], "5-0-1")
        self.assertEqual(decoded["metadata"]["layer_count"], 6)
        self.assertEqual(decoded["metadata"]["value_groups_per_layer"], [1, 1, 1, 1, 1, 1])
        self.assertEqual(decoded["metadata"]["iteration_counts"], [2, 2, 1, 1, 2, 1])
        self.assertEqual(decoded["metadata"]["value_group_values"], [0, 1, 1, 1, 2, 0])
        self.assertEqual([row["identifier"] for row in decoded["rows"]], ["0-0-1", "0-0-2", "1-1-1", "1-1-2", "2-1-1", "3-1-1", "4-2-1", "4-2-2", "5-0-1"])
        self.assertEqual(decoded["cobm"][-1]["active_identifiers"], ["4-2-1", "4-2-2"])

    def test_foreign_resolution_uses_contract_mss_context(self):
        mod = _load_shared_mss()
        compiled = mod.compile_mss_payload(_example_payload(), ["4-2-1", "4-2-2"])
        resolved = mod.resolve_contract_datum_ref(
            f"{REMOTE_MSN_ID}.5-0-1",
            local_msn_id="3-2-3-17-77-1-6-4-1-4",
            anthology_payload={},
            contract_payloads=[
                {
                    "contract_id": "contract-demo",
                    "owner_msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "counterparty_msn_id": REMOTE_MSN_ID,
                    "counterparty_mss": compiled["bitstring"],
                }
            ],
        )

        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["scope"], "contract_mss")
        self.assertEqual(resolved["contract_id"], "contract-demo")
        self.assertEqual(resolved["row"]["identifier"], "5-0-1")


if __name__ == "__main__":
    unittest.main()
