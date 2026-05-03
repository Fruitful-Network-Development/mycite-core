from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.fnd_ebi_donations_read_only import (
    FndEbiDonationsReadOnlyRequest,
    FndEbiDonationsReadOnlyResult,
    FndEbiDonationsReadOnlySource,
)


class FndEbiDonationsReadOnlyContractTests(unittest.TestCase):
    def test_request_normalizes_domain_and_tenant_id(self) -> None:
        request = FndEbiDonationsReadOnlyRequest(
            portal_tenant_id="FND",
            selected_domain="CuyahogaValleyCountrysideConservancy.ORG",
        )

        self.assertEqual(
            request.to_dict(),
            {
                "portal_tenant_id": "fnd",
                "selected_domain": "cuyahogavalleycountrysideconservancy.org",
            },
        )

    def test_request_rejects_invalid_domain(self) -> None:
        with self.assertRaisesRegex(ValueError, "selected_domain"):
            FndEbiDonationsReadOnlyRequest(
                portal_tenant_id="fnd",
                selected_domain="../cuyahogavalleycountrysideconservancy.org",
            )

    def test_request_requires_portal_tenant_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "portal_tenant_id"):
            FndEbiDonationsReadOnlyRequest(portal_tenant_id="")

    def test_request_allows_empty_selected_domain(self) -> None:
        request = FndEbiDonationsReadOnlyRequest(portal_tenant_id="fnd")
        self.assertEqual(request.selected_domain, "")

    def test_source_rejects_empty_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty dict"):
            FndEbiDonationsReadOnlySource(payload={})

    def test_source_accepts_valid_payload(self) -> None:
        source = FndEbiDonationsReadOnlySource(
            payload={
                "portal_tenant_id": "fnd",
                "profiles": [{"domain": "cuyahogavalleycountrysideconservancy.org"}],
            }
        )
        self.assertEqual(source.payload["portal_tenant_id"], "fnd")

    def test_result_found_is_true_when_source_is_set(self) -> None:
        source = FndEbiDonationsReadOnlySource(
            payload={
                "portal_tenant_id": "fnd",
                "profiles": [],
            }
        )
        result = FndEbiDonationsReadOnlyResult(source=source)

        self.assertTrue(result.found)
        self.assertIsNotNone(result.source)

    def test_result_found_is_false_when_source_is_none(self) -> None:
        result = FndEbiDonationsReadOnlyResult(source=None)
        self.assertFalse(result.found)

    def test_result_accepts_source_as_dict(self) -> None:
        source_dict = {
            "payload": {
                "portal_tenant_id": "fnd",
                "profiles": [],
            }
        }
        result = FndEbiDonationsReadOnlyResult(source=source_dict)
        self.assertTrue(result.found)
        self.assertIsInstance(result.source, FndEbiDonationsReadOnlySource)

    def test_result_to_dict_round_trip(self) -> None:
        source = FndEbiDonationsReadOnlySource(
            payload={
                "portal_tenant_id": "fnd",
                "profiles": [{"domain": "cuyahogavalleycountrysideconservancy.org"}],
            }
        )
        result = FndEbiDonationsReadOnlyResult(source=source)
        as_dict = result.to_dict()
        self.assertTrue(as_dict["found"])
        self.assertEqual(as_dict["source"]["payload"]["portal_tenant_id"], "fnd")


if __name__ == "__main__":
    unittest.main()
