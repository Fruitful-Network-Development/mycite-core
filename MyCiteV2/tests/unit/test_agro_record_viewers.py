"""Phase-3 record viewers (invoices / contacts / plots) — registration + live shape.

Each is a DatumDocTool subclass emitting a declarative container payload. The pure
checks confirm registration + the container discriminator; the live checks confirm the
payload resolves names against the reconciled lcl (Phase 1b).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.tools import get as tools_get
from MyCiteV2.packages.tools._contract import DatumDocTool

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


class TestRecordViewersRegistered(unittest.TestCase):
    def test_registered_as_datum_doc_tools(self) -> None:
        for tid, container in (("invoices", "record_table"), ("contacts", "record_list"), ("plots", "record_table")):
            tool = tools_get(tid)
            self.assertIsInstance(tool, DatumDocTool, tid)
            self.assertEqual(tool.container, container, tid)
            self.assertTrue(tool.applies_to_archetype, tid)


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestRecordViewersLive(unittest.TestCase):
    def _payload(self, tid: str) -> dict:
        return tools_get(tid).build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address=""
        )

    def test_invoices_resolves_lines(self) -> None:
        p = self._payload("invoices")
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["container"], "record_table")
        self.assertGreater(p["row_count"], 0)
        # invoice refs resolve to names now that 1-4-* exist (Phase 1b reconcile).
        self.assertTrue(all(not r["invoice"].startswith("1-4-") for r in p["rows"]))

    def test_contacts_resolves_suppliers(self) -> None:
        p = self._payload("contacts")
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["container"], "record_list")
        self.assertGreater(p["item_count"], 0)
        self.assertTrue(all(not it["title"].startswith("1-1-4-") for it in p["items"]))

    def test_plots_lists_features(self) -> None:
        p = self._payload("plots")
        self.assertIsNone(p.get("error"))
        self.assertEqual(p["container"], "record_table")
        self.assertGreater(p["row_count"], 0)
        self.assertIn("polygon", p["columns"])

    def test_phase5_seed_doc_viewers(self) -> None:
        for tid, col in (("livestock", "animal"), ("equipment", "equipment"),
                         ("soil", "soil_type"), ("growing_season", "season")):
            p = self._payload(tid)
            self.assertIsNone(p.get("error"), tid)
            self.assertEqual(p["container"], "record_table", tid)
            self.assertGreater(p["row_count"], 0, tid)
            self.assertIn(col, p["columns"], tid)


if __name__ == "__main__":
    unittest.main()
