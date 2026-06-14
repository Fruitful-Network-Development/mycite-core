from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store.contracts import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.lens.base import BinaryTextLens
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools.contracts_tool import (
    _NOMINAL_BITS,
    _RF_LCL_ID,
    _RF_NOMINAL,
    ContractsTool,
    _draw_down,
    _encode_bits,
    _invoice_weights,
    _parse_weight,
    build_contract_row,
)
from MyCiteV2.packages.tools.product_document_view import LclNameIndex

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")
_BIN = BinaryTextLens()


def _invoices_doc(rows: list[dict]) -> AuthoritativeDatumDocument:
    return AuthoritativeDatumDocument(
        document_id="lv.3-2-3-17-77-1-6-4-1-4.agro_erp.invoices." + "a" * 64,
        source_kind="sandbox_source",
        document_name="invoices",
        relative_path="sandbox/agro-erp/invoices.json",
        canonical_name="invoices",
        document_metadata={"schema": "mycite.v2.datum.agro_erp.invoices.v1"},
        rows=tuple(AuthoritativeDatumDocumentRow.from_dict(r) for r in rows),
    )


class TestContractsPure(unittest.TestCase):
    def test_registered_with_schema_archetype(self) -> None:
        self.assertIsInstance(tools_get("contracts"), ContractsTool)
        self.assertEqual(ContractsTool.applies_to_archetype, ("mycite.v2.datum.agro_erp.contracts.v1",))

    def test_build_contract_row_shape(self) -> None:
        row = build_contract_row(
            "4-5-1", hops_date="2025-001-008", invoice_node="1-4-1", plot_node="1-2-4",
            amount="10 lbs", cost="$50.00", label="contract_1",
        )
        head = row.raw[0]
        self.assertEqual(head[0], "4-5-1")
        # 5 pairs => head length 11; markers in order.
        self.assertEqual(len(head), 11)
        self.assertEqual(head[1], "rf.3-1-6")  # date
        self.assertEqual(head[2], "2025-001-008")
        self.assertEqual(head[3], "rf.3-1-5")  # invoice_id
        self.assertEqual(head[4], "1-4-1")
        self.assertEqual(head[5], "rf.3-1-5")  # plot_id
        self.assertEqual(head[6], "1-2-4")
        self.assertEqual(head[7], "rf.3-1-7")  # amount
        self.assertEqual(head[9], "rf.3-1-7")  # cost
        self.assertEqual(row.raw[1], ["contract_1"])
        # amount round-trips through the nominal decode.
        self.assertEqual(_BIN.decode(head[8]), "10 lbs")
        self.assertEqual(_BIN.decode(head[10]), "$50.00")

    def test_parse_weight(self) -> None:
        self.assertEqual(_parse_weight("25 lbs"), 25.0)
        self.assertEqual(_parse_weight("$95.00"), 95.0)
        self.assertEqual(_parse_weight("500 slips"), 500.0)
        self.assertEqual(_parse_weight(""), 0.0)

    def test_draw_down_keeps_uncommitted_invoice_visible(self) -> None:
        # inv2 has purchased weight but no contract; once inv1 has a contract the old
        # code dropped inv2 from the draw-down. It must stay, at full remaining capacity.
        inv_weights = {
            "1-4-1": {"label": "inv1", "weight": 100.0},
            "1-4-2": {"label": "inv2", "weight": 50.0},
        }
        committed = {"1-4-1": 30.0}
        rows = _draw_down(inv_weights, committed)
        self.assertEqual({r["invoice"] for r in rows}, {"inv1", "inv2"})
        inv2 = next(r for r in rows if r["invoice"] == "inv2")
        self.assertEqual(inv2["committed"], 0.0)
        self.assertEqual(inv2["remaining"], 50.0)
        self.assertFalse(inv2["over_committed"])
        inv1 = next(r for r in rows if r["invoice"] == "inv1")
        self.assertEqual(inv1["remaining"], 70.0)

    def test_draw_down_flags_over_commit(self) -> None:
        rows = _draw_down({"1-4-1": {"label": "inv1", "weight": 10.0}}, {"1-4-1": 25.0})
        self.assertTrue(rows[0]["over_committed"])
        self.assertEqual(rows[0]["remaining"], -15.0)

    def test_invoice_weights_marker_order_independent(self) -> None:
        # Markers emitted in a non-canonical order (nominal weight BEFORE the lcl id):
        # the decode is marker-driven, not positional, so the weight is still found.
        weight_bits = _encode_bits("40 lbs", bits=_NOMINAL_BITS)
        doc = _invoices_doc([
            {"datum_address": "4-6-1",
             "raw": [["4-6-1", _RF_NOMINAL, weight_bits, _RF_LCL_ID, "1-4-1"], ["invoice_1"]]},
        ])
        weights = _invoice_weights(doc, LclNameIndex(None))
        self.assertIn("1-4-1", weights)
        self.assertEqual(weights["1-4-1"]["weight"], 40.0)


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestContractsLive(unittest.TestCase):
    def test_contracts_drawdown_invariants(self) -> None:
        # Robust to however many contracts the live doc holds (the contract builder may
        # have committed some): assert the draw-down ARITHMETIC invariants rather than a
        # pristine-empty baseline.
        payload = ContractsTool().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address=""
        )
        self.assertIsNone(payload.get("error"))
        self.assertEqual(payload["schema"], "mycite.v2.portal.workbench.tool.contracts.v1")
        self.assertEqual(payload["contract_count"], len(payload["contracts"]))
        self.assertGreaterEqual(payload["contract_count"], 0)
        self.assertGreater(len(payload["draw_down"]), 0)
        for d in payload["draw_down"]:
            self.assertGreaterEqual(d["committed"], 0.0)
            self.assertAlmostEqual(d["remaining"], d["purchased_weight"] - d["committed"], places=6)
            self.assertEqual(d["over_committed"], d["committed"] > d["purchased_weight"])


if __name__ == "__main__":
    unittest.main()
