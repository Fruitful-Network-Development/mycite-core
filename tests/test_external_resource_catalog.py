from __future__ import annotations

import unittest

from portals._shared.portal.data_engine.external_resources.contact_card_catalog import parse_public_resource_catalog


class ExternalResourceCatalogTests(unittest.TestCase):
    def test_parses_public_resource_and_accessible_entries(self):
        payload = {
            "msn_id": "9-9-9-9",
            "public_resources": [
                {
                    "resource_id": "farm_metrics",
                    "kind": "datum_export",
                    "export_family": "mycite.public.resource.v1",
                    "href": "https://example.test/farm_metrics.json",
                    "lens_hint": "datum",
                }
            ],
            "accessible": {"9-9-9-9.5-0-1": {"display_title": "Farm Metric"}},
        }
        resources = parse_public_resource_catalog(payload, source_msn_id="9-9-9-9")
        ids = {item.resource_id for item in resources}
        self.assertIn("farm_metrics", ids)
        self.assertTrue(any(item.resource_id.startswith("accessible:") for item in resources))


if __name__ == "__main__":
    unittest.main()
