from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store import (
    PUBLICATION_TENANT_SUMMARY_SOURCE_SCHEMA,
    PublicationTenantSummaryRequest,
    PublicationTenantSummaryResult,
    PublicationTenantSummarySource,
)


class PublicationTenantSummaryContractTests(unittest.TestCase):
    def test_request_source_and_result_are_serializable(self) -> None:
        request = PublicationTenantSummaryRequest.from_dict(
            {"tenant_id": "TFF", "tenant_domain": "TrappFamilyFarm.com"}
        )
        source = PublicationTenantSummarySource(
            tenant_id=request.tenant_id,
            tenant_domain=request.tenant_domain,
            profile_id="3-2-3-17-77-2-6-3-1-6",
            public_profile={"title": "trapp_family_farm"},
            tenant_profile={"summary": "Trusted-tenant summary"},
        )
        result = PublicationTenantSummaryResult(
            source=source,
            resolution_status={"anthology": "loaded", "domain_match": "matched"},
            warnings=("loaded",),
        )

        self.assertEqual(request.tenant_id, "tff")
        self.assertEqual(request.tenant_domain, "trappfamilyfarm.com")
        payload = result.to_dict()
        self.assertTrue(payload["found"])
        self.assertEqual(payload["source"]["schema"], PUBLICATION_TENANT_SUMMARY_SOURCE_SCHEMA)
        self.assertEqual(json.loads(json.dumps(payload, sort_keys=True)), payload)

    def test_contracts_reject_missing_identity_or_non_json_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "tenant_id is required"):
            PublicationTenantSummaryRequest.from_dict({"tenant_id": "", "tenant_domain": "example.com"})

        with self.assertRaisesRegex(ValueError, "tenant_domain must be a domain-like value"):
            PublicationTenantSummaryRequest.from_dict({"tenant_id": "tff", "tenant_domain": ""})

        with self.assertRaisesRegex(ValueError, "profile_id is required"):
            PublicationTenantSummarySource(
                tenant_id="tff",
                tenant_domain="trappfamilyfarm.com",
                profile_id="",
                public_profile=None,
                tenant_profile=None,
            )

        with self.assertRaisesRegex(ValueError, "must be JSON-serializable"):
            PublicationTenantSummaryResult(
                source=None,
                resolution_status={"bad": object()},
            )


if __name__ == "__main__":
    unittest.main()
