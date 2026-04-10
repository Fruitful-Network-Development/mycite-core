from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


REMOTE_MSN_ID = "3-2-3-17-77-2-6-3-1-6"


def _load_shared_mss():
    repo_root = Path(__file__).resolve().parents[1]
    token = str(repo_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("mycite_core.mss_resolution")


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

class MssContractContextTests(unittest.TestCase):
    def test_compile_decode_and_root_selection_round_trip(self):
        mod = _load_shared_mss()
        compiled = mod.compile_mss_payload(_example_payload(), ["4-2-1", "4-2-2"])

        self.assertTrue(compiled["bitstring"])
        self.assertEqual(compiled["wire_variant"], "canonical")
        self.assertEqual(compiled["root_identifier"], "5-0-1")
        self.assertEqual(compiled["selected_compact_refs"], ["4-2-1", "4-2-2"])
        self.assertTrue(len(compiled["cobm"]) >= 1)
        self.assertIn("source_identifier", compiled["rows"][-1])
        self.assertTrue(compiled["source_identifiers"])

        decoded = mod.decode_mss_payload(compiled["bitstring"])
        self.assertEqual(decoded["wire_variant"], "canonical")
        row_ids = [row["identifier"] for row in decoded["rows"]]
        self.assertIn("5-0-1", row_ids)
        root_row = next(row for row in decoded["rows"] if row["identifier"] == "5-0-1")
        self.assertEqual([pair["reference"] for pair in root_row["pairs"]], ["4-2-1", "4-2-2"])
        self.assertEqual(decoded["metadata"]["layer_count"], 6)

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

    def test_hyphae_decode_uses_explicit_source_identifier_sidecar_for_resolution(self):
        mod = _load_shared_mss()
        payload = {
            "0-0-1": [["0-0-1", "0", "0"], ["a"]],
            "0-0-5": [["0-0-5", "0", "0"], ["b"]],
            "1-1-1": [["1-1-1", "0-0-5", "1"], ["l1"]],
            "2-1-1": [["2-1-1", "1-1-1", "1"], ["l2"]],
            "3-1-1": [["3-1-1", "2-1-1", "1"], ["l3"]],
        }
        compiled = mod.compile_mss_payload(payload, ["3-1-1"])
        decoded = mod.decode_mss_payload(compiled["bitstring"], source_identifiers=compiled["source_identifiers"])
        row = next((item for item in decoded.get("rows") or [] if item.get("identifier") == "0-0-1"), {})
        self.assertEqual(row.get("source_identifier"), "0-0-5")
        resolved = mod.resolve_contract_datum_ref(
            f"{REMOTE_MSN_ID}.0-0-5",
            local_msn_id="3-2-3-17-77-1-6-4-1-4",
            anthology_payload={},
            contract_payloads=[
                {
                    "contract_id": "contract-demo",
                    "owner_msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "counterparty_msn_id": REMOTE_MSN_ID,
                    "counterparty_mss": compiled["bitstring"],
                    "counterparty_source_identifiers": compiled["source_identifiers"],
                }
            ],
        )
        self.assertTrue(resolved["ok"])
        self.assertEqual((resolved.get("row") or {}).get("source_identifier"), "0-0-5")

    def test_compile_rejects_non_v2_payloads_instead_of_silent_fallback(self):
        mod = _load_shared_mss()
        payload = {
            "0-0-1": [["0-0-1", "0", "0"], ["top"]],
            "1-1-1": [["1-1-1", "0-0-1", "not-an-integer"], ["broken"]],
        }
        with self.assertRaises(ValueError):
            mod.compile_mss_payload(payload, ["1-1-1"])

    def test_foreign_resolution_requires_preferred_contract_when_multiple_match(self):
        mod = _load_shared_mss()
        compiled = mod.compile_mss_payload(_example_payload(), ["4-2-1"])
        resolved = mod.resolve_contract_datum_ref(
            f"{REMOTE_MSN_ID}.5-0-1",
            local_msn_id="3-2-3-17-77-1-6-4-1-4",
            anthology_payload={},
            contract_payloads=[
                {
                    "contract_id": "contract-a",
                    "owner_msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "counterparty_msn_id": REMOTE_MSN_ID,
                    "counterparty_mss": compiled["bitstring"],
                },
                {
                    "contract_id": "contract-b",
                    "owner_msn_id": "3-2-3-17-77-1-6-4-1-4",
                    "counterparty_msn_id": REMOTE_MSN_ID,
                    "counterparty_mss": compiled["bitstring"],
                },
            ],
        )
        self.assertFalse(resolved["ok"])
        self.assertIn("preferred_contract_id", str(resolved.get("error") or ""))


if __name__ == "__main__":
    unittest.main()
