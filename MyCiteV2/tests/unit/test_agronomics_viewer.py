"""Agronomics composite tool — composes farm_profile + the LCL structure viewer.

It renders nothing itself: build_panel_payload calls the two sub-viewers and returns their
payloads as ``container:"composite"`` panes (farm_profile left, LCL right). Tests the
composition + pane wiring (sub-viewers monkeypatched) and the live two-pane payload.
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
                mock.patch.object(av.SamrasStructureViewer, "build_panel_payload",
                                  return_value={"schema": "lcl", "structure": "lcl"}) as ss:
            payload = av.AgronomicsViewer().build_panel_payload(
                authority_db_file=None, sandbox_id="agro_erp",
                document_id="", datum_address="", extra_query=extra_query,
            )
        return payload, fp, ss

    def test_two_panes_in_order(self) -> None:
        payload, _fp, _ss = self._build(None)
        self.assertEqual(payload["container"], "composite")
        self.assertEqual([p["tool_id"] for p in payload["panes"]], ["farm_profile", "samras_structure"])
        self.assertEqual([p["label"] for p in payload["panes"]], ["Farm Profile", "LCL ID Space"])
        self.assertEqual(payload["panes"][0]["panel_payload"], {"schema": "fp", "feature_count": 3})
        self.assertEqual(payload["panes"][1]["panel_payload"], {"schema": "lcl", "structure": "lcl"})

    def test_right_pane_defaults_to_lcl(self) -> None:
        _payload, _fp, ss = self._build(None)
        self.assertEqual(ss.call_args.kwargs["extra_query"], {"samras_structure": "lcl"})

    def test_structure_override_passes_through(self) -> None:
        _payload, _fp, ss = self._build({"samras_structure": "txa"})
        self.assertEqual(ss.call_args.kwargs["extra_query"], {"samras_structure": "txa"})


@unittest.skipUnless(_LIVE_DB.exists(), "live MOS not present")
class TestLive(unittest.TestCase):
    def test_live_two_panes(self) -> None:
        payload = av.AgronomicsViewer().build_panel_payload(
            authority_db_file=_LIVE_DB, sandbox_id="agro_erp", document_id="", datum_address="",
        )
        self.assertEqual(payload["container"], "composite")
        self.assertEqual([p["tool_id"] for p in payload["panes"]], ["farm_profile", "samras_structure"])
        farm = payload["panes"][0]["panel_payload"]
        lcl = payload["panes"][1]["panel_payload"]
        self.assertIsNone(farm.get("error"))
        self.assertIn("feature_collection", farm)
        self.assertIsNone(lcl.get("error"))
        self.assertEqual(lcl["structure"], "lcl")
        self.assertGreaterEqual(lcl["denoted_count"], 4665)


if __name__ == "__main__":
    unittest.main()
