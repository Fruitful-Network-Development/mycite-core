"""Record Synopsis / Inventory Synopsis — registration + live derived figures."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import MyCiteV2.packages.tools.record_synopsis as rs
from MyCiteV2.instances._shared.runtime.portal_palette_runtime import LIVE_TOOL_IDS
from MyCiteV2.packages.tools import get as tools_get

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


class TestRegistration(unittest.TestCase):
    def test_registered_and_live(self) -> None:
        tool = tools_get("inventory_synopsis")
        self.assertIsInstance(tool, rs.InventorySynopsis)
        self.assertEqual(tool.container, "synopsis")
        self.assertIn("inventory_synopsis", LIVE_TOOL_IDS)


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLive(unittest.TestCase):
    def test_inventory_figures(self) -> None:
        p = rs.InventorySynopsis().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address="",
        )
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["container"], "synopsis")
        # Procurement invoices exist → at least one product with a derived unit count.
        self.assertGreater(p["item_count"], 0)
        for it in p["items"]:
            self.assertIn("label", it)
            self.assertIsInstance(it["figure"], int)
            self.assertGreaterEqual(it["figure"], 0)
        # figures are sorted descending.
        figs = [it["figure"] for it in p["items"]]
        self.assertEqual(figs, sorted(figs, reverse=True))


if __name__ == "__main__":
    unittest.main()
