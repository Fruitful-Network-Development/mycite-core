from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.fnd_ebi_read_only import (
    FndEbiReadOnlyRequest,
    FndEbiReadOnlyResult,
    FndEbiReadOnlySource,
)


class FndEbiReadOnlyContractTests(unittest.TestCase):
    def test_request_normalizes_domain_and_year_month(self) -> None:
        request = FndEbiReadOnlyRequest(
            portal_tenant_id="FND",
            selected_domain="FruitfulNetworkDevelopment.com",
            year_month="2026-04",
        )

        self.assertEqual(
            request.to_dict(),
            {
                "portal_tenant_id": "fnd",
                "selected_domain": "fruitfulnetworkdevelopment.com",
                "year_month": "2026-04",
            },
        )

    def test_request_rejects_invalid_domain_and_month(self) -> None:
        with self.assertRaisesRegex(ValueError, "selected_domain"):
            FndEbiReadOnlyRequest(
                portal_tenant_id="fnd",
                selected_domain="../fruitfulnetworkdevelopment.com",
            )

        with self.assertRaisesRegex(ValueError, "year_month"):
            FndEbiReadOnlyRequest(
                portal_tenant_id="fnd",
                year_month="2026/04",
            )

    def test_source_payload_must_be_non_empty_json(self) -> None:
        source = FndEbiReadOnlySource(
            payload={
                "portal_tenant_id": "fnd",
                "profiles": [{"domain": "fruitfulnetworkdevelopment.com"}],
            }
        )
        result = FndEbiReadOnlyResult(source=source)

        self.assertTrue(result.found)
        self.assertEqual(result.to_dict()["source"]["payload"]["portal_tenant_id"], "fnd")

        with self.assertRaisesRegex(ValueError, "non-empty dict"):
            FndEbiReadOnlySource(payload={})


if __name__ == "__main__":
    unittest.main()
