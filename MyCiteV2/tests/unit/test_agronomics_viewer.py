"""Agronomics tool — FARM/PLAN/NETWORK tabs; FARM composes farm_profile + the LCL viewer.

It renders nothing itself: build_panel_payload returns a ``container:"tabbed"`` payload whose
FARM tab is a ``container:"composite"`` of the two sub-viewers (farm_profile left, LCL right)
and whose PLAN/NETWORK tabs are blank scaffolds. Tests the tab + composition wiring
(sub-viewers monkeypatched) and the live payload.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import MyCiteV2.packages.tools.agronomics_viewer as av
from MyCiteV2.packages.tools import get as tools_get

_LIVE_DB = Path("/srv/webapps/mycite/fnd/private/mos_authority.sqlite3")


class TestRegistration(unittest.TestCase):
    def test_registered(self) -> None:
        self.assertIsInstance(tools_get("agronomics"), av.AgronomicsViewer)
        self.assertEqual(
            set(av.AgronomicsViewer.applies_to_archetype),
            {"hops_geospatial_filament", "samras_taxonomy"},
        )
        self.assertTrue(getattr(av.AgronomicsViewer, "wants_surface_query", False))


class TestComposition(unittest.TestCase):
    def _build(self, extra_query):
        with mock.patch.object(av.FarmProfileViewer, "build_panel_payload",
                               return_value={"schema": "fp", "feature_count": 3}) as fp, \
                mock.patch.object(av.LocalDomainViewer, "build_panel_payload",
                                  return_value={"schema": "lcl", "structure": "lcl"}) as ss:
            payload = av.AgronomicsViewer().build_panel_payload(
                authority_db_file=None, sandbox_id="agro_erp",
                document_id="", datum_address="", extra_query=extra_query,
            )
        return payload, fp, ss

    def test_two_panes_in_order(self) -> None:
        payload, _fp, _ss = self._build(None)
        # FARM/PLAN/NETWORK tabs; FARM is the composite of the two sub-viewers.
        self.assertEqual(payload["container"], "tabbed")
        self.assertEqual([t["id"] for t in payload["tabs"]], ["farm", "plan", "network"])
        self.assertEqual(payload["active_tab"], "farm")
        farm = payload["tabs"][0]["panel_payload"]
        self.assertEqual(farm["container"], "composite")
        self.assertEqual([p["tool_id"] for p in farm["panes"]], ["farm_profile", "local_domain"])
        self.assertEqual([p["label"] for p in farm["panes"]], ["Farm Profile", "Local Domain"])
        self.assertEqual(farm["panes"][0]["panel_payload"], {"schema": "fp", "feature_count": 3})
        self.assertEqual(farm["panes"][1]["panel_payload"], {"schema": "lcl", "structure": "lcl"})
        # PLAN is a composite of a planting scaffold + the far-right Inventory synopsis.
        plan = payload["tabs"][1]["panel_payload"]
        self.assertEqual(plan["container"], "composite")
        self.assertEqual([p["tool_id"] for p in plan["panes"]], ["planting", "inventory_synopsis"])
        # NETWORK stays a blank scaffold.
        self.assertIsNone(payload["tabs"][2]["panel_payload"])

    def test_right_pane_defaults_to_lcl(self) -> None:
        _payload, _fp, ss = self._build(None)
        self.assertEqual(ss.call_args.kwargs["extra_query"], {"samras_structure": "lcl"})

    def test_structure_override_passes_through(self) -> None:
        _payload, _fp, ss = self._build({"samras_structure": "txa"})
        self.assertEqual(ss.call_args.kwargs["extra_query"], {"samras_structure": "txa"})

    def test_local_view_full_tab_takeover(self) -> None:
        # local_view=<token> swaps the FARM tab from the composite into the node's record
        # table (full-tab) with a back affordance; PLAN/NETWORK are untouched.
        table = {"container": "record_table", "title": "Product Type", "columns": ["lcl_id"], "rows": []}
        with mock.patch.object(av, "build_record_view", return_value=table) as brv:
            payload = av.AgronomicsViewer().build_panel_payload(
                authority_db_file=None, sandbox_id="agro_erp", document_id="", datum_address="",
                extra_query={"local_view": "product"},
            )
        brv.assert_called_once()
        self.assertEqual(brv.call_args.args[0], "product")
        farm = payload["tabs"][0]["panel_payload"]
        self.assertEqual(farm["container"], "record_table")
        self.assertEqual(farm["back"], {"label": "Back to farm view", "param": "local_view", "value": ""})
        self.assertEqual([t["id"] for t in payload["tabs"]], ["farm", "plan", "network"])

    def test_unknown_local_view_falls_back_to_composite(self) -> None:
        # build_record_view returns None for an unknown token → composite (no takeover).
        with mock.patch.object(av.FarmProfileViewer, "build_panel_payload", return_value={"schema": "fp"}), \
                mock.patch.object(av.LocalDomainViewer, "build_panel_payload", return_value={"schema": "lcl"}):
            payload = av.AgronomicsViewer().build_panel_payload(
                authority_db_file=None, sandbox_id="agro_erp", document_id="", datum_address="",
                extra_query={"local_view": "nope"},
            )
        self.assertEqual(payload["tabs"][0]["panel_payload"]["container"], "composite")


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLive(unittest.TestCase):
    def test_live_two_panes(self) -> None:
        payload = av.AgronomicsViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address="",
        )
        self.assertEqual(payload["container"], "tabbed")
        farm_tab = payload["tabs"][0]["panel_payload"]
        self.assertEqual(farm_tab["container"], "composite")
        self.assertEqual([p["tool_id"] for p in farm_tab["panes"]], ["farm_profile", "local_domain"])
        farm = farm_tab["panes"][0]["panel_payload"]
        lcl = farm_tab["panes"][1]["panel_payload"]
        self.assertIsNone(farm.get("error"))
        self.assertIn("feature_collection", farm)
        self.assertIsNone(lcl.get("error"))
        self.assertEqual(lcl["structure"], "lcl")
        self.assertEqual(lcl["container"], "local_tree")
        # The live lcl id-space is large; assert a robust lower bound rather than an exact
        # count (the tree is re-authored by the restructure migration).
        self.assertGreaterEqual(lcl["denoted_count"], 2000)


if __name__ == "__main__":
    unittest.main()
