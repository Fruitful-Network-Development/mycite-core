from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


def _load_resolver_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.data_engine.property_workspace")


class PropertyWorkspaceResolverTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_resolver_module()

    def test_resolve_property_workspace_from_config_and_rows(self):
        config = {
            "property": [
                {
                    "title": "parcel-a",
                    "bbox": ["4-1-4", "4-1-5"],
                    "geometry": {"type": "Polygon", "coordinates": ["4-1-6", "4-1-7", "4-1-8", "4-1-6"]},
                }
            ]
        }
        rows_by_id = {
            "4-1-4": {"identifier": "4-1-4", "label": "bbox-1", "pairs": [{"reference": "3-1-4", "magnitude": "CF67E2F01893AD7E"}]},
            "4-1-5": {"identifier": "4-1-5", "label": "bbox-2", "pairs": [{"reference": "3-1-4", "magnitude": "CF69230E1894CAD8"}]},
            "4-1-6": {"identifier": "4-1-6", "label": "coordinate-1", "pairs": [{"reference": "3-1-4", "magnitude": "CF69268F1894171F"}]},
            "4-1-7": {"identifier": "4-1-7", "label": "coordinate-2", "pairs": [{"reference": "3-1-4", "magnitude": "CF6927F21894C898"}]},
            "4-1-8": {"identifier": "4-1-8", "label": "coordinate-3", "pairs": [{"reference": "3-1-4", "magnitude": "CF68E8AF1894C710"}]},
        }
        payload = self.module.resolve_property_workspace(config=config, rows_by_id=rows_by_id)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("parcel_count"), 1)
        parcel = (payload.get("parcels") or [])[0]
        self.assertEqual(parcel.get("title"), "parcel-a")
        self.assertTrue(parcel.get("valid"))
        self.assertGreaterEqual(len(parcel.get("polygon") or []), 3)
        self.assertTrue(isinstance(parcel.get("bbox_summary"), dict))
        self.assertTrue(isinstance(parcel.get("focus_hint"), dict))

    def test_numeric_coercion_handles_nested_payloads(self):
        self.assertEqual(self.module._safe_float({"value": {"longitude": "-81.234"}}), -81.234)
        self.assertEqual(self.module._safe_float({"lat": {"value": "41.111"}}), 41.111)
        self.assertEqual(self.module._safe_float(["bad", {"signed_value": "123.5"}]), 123.5)


if __name__ == "__main__":
    unittest.main()
