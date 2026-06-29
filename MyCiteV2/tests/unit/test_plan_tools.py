"""PLAN-tab tools: Plot Manager + Contract Editor (Record Studio) — registration + payload shape."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_palette_runtime import LIVE_TOOL_IDS
from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools.plot_manager_viewer import PlotManagerViewer
from MyCiteV2.packages.tools.record_studio import ContractEditor

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


class TestRegistration(unittest.TestCase):
    def test_registered_and_live(self) -> None:
        self.assertIsInstance(tools_get("plot_manager"), PlotManagerViewer)
        self.assertIsInstance(tools_get("contract_editor"), ContractEditor)
        self.assertIn("plot_manager", LIVE_TOOL_IDS)
        self.assertIn("contract_editor", LIVE_TOOL_IDS)


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLive(unittest.TestCase):
    def test_plot_manager_payload(self) -> None:
        p = PlotManagerViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address="")
        self.assertIsNone(p.get("error"))
        self.assertIn("feature_collection", p)
        self.assertTrue(p.get("today"))
        self.assertEqual(p.get("create_route"), "/portal/api/v2/agro/create_cluster")
        # plot features carry their lcl node for selection → cluster.
        self.assertTrue(any(f["properties"].get("lcl_node")
                            for f in p["feature_collection"]["features"] if f["properties"]["kind"] == "plot"))

    def test_contract_editor_form(self) -> None:
        p = ContractEditor().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address="")
        self.assertEqual(p["container"], "record_form")
        self.assertEqual([f["key"] for f in p["fields"]],
                         ["date", "invoice_node", "referent_node", "amount", "cost"])
        # referent select offers plots (and clusters when they exist).
        ref = next(f for f in p["fields"] if f["key"] == "referent_node")
        self.assertTrue(any(o["value"].startswith("1-2-4-") for o in ref["options"]))
        self.assertEqual(p["submit_action"]["route"], "/portal/api/v2/agro/save_contract")


if __name__ == "__main__":
    unittest.main()
