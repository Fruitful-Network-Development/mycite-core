from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.fnd_ebi import FndEbiReadOnlyService
from MyCiteV2.packages.ports.fnd_ebi_read_only import (
    FndEbiReadOnlyResult,
    FndEbiReadOnlySource,
)


class _FakeFndEbiPort:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests = []

    def read_fnd_ebi_read_only(self, request):
        self.requests.append(request)
        return FndEbiReadOnlyResult(source=FndEbiReadOnlySource(payload=self.payload))


class FndEbiReadOnlyUnitTests(unittest.TestCase):
    def test_service_prefers_requested_domain_then_tenant_domain(self) -> None:
        payload = {
            "portal_tenant_id": "fnd",
            "year_month": "2026-04",
            "profiles": [
                {
                    "domain": "fruitfulnetworkdevelopment.com",
                    "profile_file": "/private/fnd-ebi.fnd.json",
                    "site_root": "/srv/webapps/clients/fruitfulnetworkdevelopment.com/site",
                    "analytics_root": "/srv/webapps/clients/fruitfulnetworkdevelopment.com/analytics",
                    "health_label": "ready",
                    "traffic": {"requests_30d": 10},
                    "events_summary": {"events_30d": 4},
                    "errors_noise": {},
                    "access_log": {"state": "ready"},
                    "error_log": {"state": "ready"},
                    "events_file": {"state": "ready"},
                    "freshness": {},
                    "warnings": [],
                },
                {
                    "domain": "trappfamilyfarm.com",
                    "profile_file": "/private/fnd-ebi.tff.json",
                    "site_root": "/srv/webapps/clients/trappfamilyfarm.com/site",
                    "analytics_root": "/srv/webapps/clients/trappfamilyfarm.com/analytics",
                    "health_label": "attention_required",
                    "traffic": {"requests_30d": 2},
                    "events_summary": {"events_30d": 0},
                    "errors_noise": {},
                    "access_log": {"state": "ready"},
                    "error_log": {"state": "ready"},
                    "events_file": {"state": "missing"},
                    "freshness": {},
                    "warnings": ["events file is missing for the selected month"],
                },
            ],
            "warnings": ["shared warning"],
        }
        service = FndEbiReadOnlyService(_FakeFndEbiPort(payload))

        tenant_selected = service.read_surface(
            portal_tenant_id="fnd",
            portal_tenant_domain="fruitfulnetworkdevelopment.com",
            year_month="2026-04",
        )
        requested_selected = service.read_surface(
            portal_tenant_id="fnd",
            portal_tenant_domain="fruitfulnetworkdevelopment.com",
            selected_domain="trappfamilyfarm.com",
            year_month="2026-04",
        )

        self.assertEqual(tenant_selected["selected_domain"], "fruitfulnetworkdevelopment.com")
        self.assertEqual(tenant_selected["overview"]["health_label"], "ready")
        self.assertEqual(requested_selected["selected_domain"], "trappfamilyfarm.com")
        self.assertIn("shared warning", requested_selected["warnings"])
        self.assertIn("events file is missing for the selected month", requested_selected["warnings"])
        self.assertEqual(len(requested_selected["profile_cards"]), 2)


if __name__ == "__main__":
    unittest.main()
