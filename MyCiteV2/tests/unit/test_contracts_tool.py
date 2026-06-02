from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.lens.base import BinaryTextLens
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools.contracts_tool import (
    ContractsTool,
    _parse_weight,
    build_contract_row,
)

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")
_BIN = BinaryTextLens()


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


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestContractsLive(unittest.TestCase):
    def test_empty_contracts_with_drawdown_baseline(self) -> None:
        payload = ContractsTool().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address=""
        )
        self.assertIsNone(payload.get("error"))
        self.assertEqual(payload["schema"], "mycite.v2.portal.workbench.tool.contracts.v1")
        # contracts doc is header-only -> 0 contracts, but the draw-down baseline lists
        # the invoice purchased weights available for commitment.
        self.assertEqual(payload["contract_count"], 0)
        self.assertGreater(len(payload["draw_down"]), 0)
        for d in payload["draw_down"]:
            self.assertEqual(d["committed"], 0.0)
            self.assertEqual(d["remaining"], d["purchased_weight"])
            self.assertFalse(d["over_committed"])


if __name__ == "__main__":
    unittest.main()
