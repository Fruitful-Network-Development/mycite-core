from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.ports.datum_store import (
    PUBLICATION_PROFILE_BASICS_WRITE_RESULT_SCHEMA,
    PublicationProfileBasicsWriteRequest,
    PublicationProfileBasicsWriteResult,
)


class PublicationProfileBasicsContractTests(unittest.TestCase):
    def test_request_and_result_are_serializable(self) -> None:
        request = PublicationProfileBasicsWriteRequest.from_dict(
            {
                "tenant_id": "TFF",
                "tenant_domain": "TrappFamilyFarm.com",
                "profile_title": "Trapp Family Farm",
                "profile_summary": "Updated summary",
                "contact_email": "hello@trappfamilyfarm.com",
                "public_website_url": "https://trappfamilyfarm.com",
            }
        )
        result = PublicationProfileBasicsWriteResult(
            source={
                "tenant_id": request.tenant_id,
                "tenant_domain": request.tenant_domain,
                "profile_id": "3-2-3-17-77-2-6-3-1-6",
                "public_profile": {"title": "trapp_family_farm"},
                "tenant_profile": {
                    "title": request.profile_title,
                    "summary": request.profile_summary,
                    "contact_email": request.contact_email,
                    "public_website_url": request.public_website_url,
                },
            },
            resolution_status={
                "anthology": "loaded",
                "domain_match": "matched",
                "public_profile": "loaded",
                "tenant_profile": "loaded",
            },
        )

        self.assertEqual(request.tenant_id, "tff")
        self.assertEqual(request.tenant_domain, "trappfamilyfarm.com")
        payload = result.to_dict()
        self.assertEqual(payload["schema"], PUBLICATION_PROFILE_BASICS_WRITE_RESULT_SCHEMA)
        self.assertEqual(payload["source"]["tenant_profile"]["contact_email"], "hello@trappfamilyfarm.com")
        self.assertEqual(json.loads(json.dumps(payload, sort_keys=True)), payload)

    def test_contracts_reject_missing_identity_or_invalid_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "tenant_id is required"):
            PublicationProfileBasicsWriteRequest.from_dict(
                {
                    "tenant_id": "",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "Title",
                }
            )

        with self.assertRaisesRegex(ValueError, "profile_title is required"):
            PublicationProfileBasicsWriteRequest.from_dict(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "",
                }
            )

        with self.assertRaisesRegex(ValueError, "tenant_domain.*plain domain-like value"):
            PublicationProfileBasicsWriteRequest.from_dict(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "bad/domain.com",
                    "profile_title": "Title",
                }
            )

        with self.assertRaisesRegex(ValueError, "must be JSON-serializable"):
            PublicationProfileBasicsWriteResult(
                source={
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_id": "3-2-3-17-77-2-6-3-1-6",
                    "public_profile": None,
                    "tenant_profile": None,
                },
                resolution_status={"bad": object()},
            )


if __name__ == "__main__":
    unittest.main()
