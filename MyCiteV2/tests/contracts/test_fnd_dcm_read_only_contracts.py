from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.fnd_dcm_read_only import (
    FndDcmReadOnlyRequest,
    FndDcmReadOnlyResult,
    FndDcmReadOnlySource,
)


class FndDcmReadOnlyContractTests(unittest.TestCase):
    def test_request_normalizes_site_and_view(self) -> None:
        request = FndDcmReadOnlyRequest(
            portal_tenant_id="FND",
            site="CuyahogaValleyCountrysideConservancy.org",
            view="pages",
            page="people",
        )

        self.assertEqual(
            request.to_dict(),
            {
                "portal_tenant_id": "fnd",
                "site": "cuyahogavalleycountrysideconservancy.org",
                "view": "pages",
                "page": "people",
                "collection": "",
            },
        )

    def test_request_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "site"):
            FndDcmReadOnlyRequest(
                portal_tenant_id="fnd",
                site="../escape.example",
            )

        with self.assertRaisesRegex(ValueError, "view"):
            FndDcmReadOnlyRequest(
                portal_tenant_id="fnd",
                view="drafts",
            )

        with self.assertRaisesRegex(ValueError, "collection"):
            FndDcmReadOnlyRequest(
                portal_tenant_id="fnd",
                collection="board profiles",
            )

    def test_source_payload_must_be_non_empty_json(self) -> None:
        source = FndDcmReadOnlySource(
            payload={
                "portal_tenant_id": "fnd",
                "profiles": [{"domain": "cuyahogavalleycountrysideconservancy.org"}],
            }
        )
        result = FndDcmReadOnlyResult(source=source)

        self.assertTrue(result.found)
        self.assertEqual(result.to_dict()["source"]["payload"]["portal_tenant_id"], "fnd")

        with self.assertRaisesRegex(ValueError, "non-empty dict"):
            FndDcmReadOnlySource(payload={})


if __name__ == "__main__":
    unittest.main()
