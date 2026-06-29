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

    def test_eligible_by_archetype_token_only_not_source_kind(self) -> None:
        # Operator model (2026-06-16): a viewer is eligible ONLY where its datum doc is
        # present, recognized by the doc's ARCHETYPE token. It must NOT claim a broad
        # source_kind ("sandbox_source") — that would surface it in every sandbox
        # (cts_gis/fnd_csm/…), all of which are sandbox_source.
        from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
            _viz_tool_matches,
        )

        record_tokens = {
            "invoices": "mycite.v2.datum.agro_erp.invoices.v1",
            "contacts": "mycite.v2.datum.agro_erp.contacts.v1",
        }
        for tid, token in record_tokens.items():
            tool = tools_get(tid)
            self.assertEqual(tool.applies_to_source_kind, (), tid)
            # Eligible for its own archetype token...
            self.assertTrue(_viz_tool_matches(tool, archetypes={token}, source_kinds=set()), tid)
            # ...but NOT for a foreign sandbox_source doc that lacks the token.
            self.assertFalse(
                _viz_tool_matches(tool, archetypes={"cts_gis_district"}, source_kinds={"sandbox_source"}),
                tid,
            )


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
        # invoice refs resolve to names (not raw lcl addresses).
        self.assertTrue(all(not r["invoice"].startswith("1-") for r in p["rows"]))
        # event-type appended (procurement) and surfaced as a resolved name.
        self.assertIn("event", p["columns"])
        self.assertTrue(all(r["event"] == "procurement" for r in p["rows"]))

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

    def test_sandbox_search_scopes_viewers_to_their_sandbox(self) -> None:
        # Operator model (2026-06-16): a viewer surfaces in the interface-panel search ONLY
        # in the sandbox holding its datum docs. The agro record viewers must be listed for
        # agro_erp but NOT for a foreign sandbox (cts_gis), even though cts_gis is also
        # sandbox_source — eligibility is by archetype token, not source_kind.
        from MyCiteV2.instances._shared.runtime.portal_palette_runtime import (
            build_sandbox_visualizers_response,
        )
        from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter

        store = SqliteSystemDatumStoreAdapter(_LIVE_DB)

        def _tool_ids(sandbox: str) -> set[str]:
            resp = build_sandbox_visualizers_response(
                tenant_id="fnd", sandbox_id=sandbox, datum_store=store
            )
            return {t["tool_id"] for t in resp.get("visualizers") or []}

        agro_ids = _tool_ids("agro_erp")
        cts_ids = _tool_ids("cts_gis")
        record_viewers = {"invoices", "contacts"}
        self.assertTrue(record_viewers <= agro_ids, f"missing from agro_erp: {record_viewers - agro_ids}")
        self.assertEqual(record_viewers & cts_ids, set(), f"leaked into cts_gis: {record_viewers & cts_ids}")


if __name__ == "__main__":
    unittest.main()
