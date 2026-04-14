from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.domains.publication import (
    PublicationTenantSummary,
    PublicationTenantSummaryService,
    normalize_publication_tenant_summary,
)
from MyCiteV2.packages.ports.datum_store import (
    PublicationTenantSummaryResult,
    PublicationTenantSummarySource,
)


class _FakePublicationTenantSummaryPort:
    def __init__(self, result: PublicationTenantSummaryResult) -> None:
        self.result = result
        self.requests = []

    def read_publication_tenant_summary(self, request):
        self.requests.append(request)
        return self.result


class PublicationTenantSummaryTests(unittest.TestCase):
    def test_normalization_uses_publication_only_fields_and_prefers_tenant_profile_copy(self) -> None:
        summary = normalize_publication_tenant_summary(
            PublicationTenantSummarySource(
                tenant_id="TFF",
                tenant_domain="TrappFamilyFarm.com",
                profile_id="3-2-3-17-77-2-6-3-1-6",
                public_profile={
                    "title": "trapp_family_farm",
                    "entity_type": "legal_entity",
                    "public_key": "hidden",
                    "options_public": {
                        "contact_email": "hello@trappfamilyfarm.com",
                    },
                },
                tenant_profile={
                    "title": "trapp_family_farm",
                    "summary": "Read-only publication summary for portal surfaces.",
                    "links": [{"href": "https://trappfamilyfarm.com"}],
                },
            ),
            warnings=("publication-only",),
        )

        payload = summary.to_dict()
        self.assertEqual(payload["tenant_id"], "tff")
        self.assertEqual(payload["tenant_domain"], "trappfamilyfarm.com")
        self.assertEqual(payload["profile_title"], "Trapp Family Farm")
        self.assertEqual(payload["profile_summary"], "Read-only publication summary for portal surfaces.")
        self.assertEqual(payload["entity_type"], "legal_entity")
        self.assertEqual(payload["contact_email"], "hello@trappfamilyfarm.com")
        self.assertEqual(payload["public_website_url"], "https://trappfamilyfarm.com")
        self.assertEqual(payload["available_documents"], ["public_profile", "tenant_profile"])
        self.assertEqual(payload["profile_resolution"], "publication_profiles_loaded")
        self.assertEqual(payload["publication_mode"], "publication-only")
        self.assertEqual(payload["warnings"], ["publication-only"])
        self.assertNotIn("public_key", json.dumps(payload, sort_keys=True))

    def test_service_reads_projection_and_returns_none_when_publication_source_is_missing(self) -> None:
        present_port = _FakePublicationTenantSummaryPort(
            PublicationTenantSummaryResult(
                source={
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_id": "3-2-3-17-77-2-6-3-1-6",
                    "public_profile": {"title": "trapp_family_farm"},
                    "tenant_profile": {"summary": "Tenant summary"},
                },
                resolution_status={"anthology": "loaded", "domain_match": "matched"},
                warnings=("loaded",),
            )
        )
        missing_port = _FakePublicationTenantSummaryPort(
            PublicationTenantSummaryResult(
                source=None,
                resolution_status={"anthology": "missing", "domain_match": "missing"},
                warnings=("missing",),
            )
        )

        present = PublicationTenantSummaryService(present_port).read_summary("tff", "trappfamilyfarm.com")
        missing = PublicationTenantSummaryService(missing_port).read_summary("tff", "trappfamilyfarm.com")

        self.assertEqual(present.to_dict()["profile_title"], "Trapp Family Farm")
        self.assertEqual(present_port.requests[0].tenant_domain, "trappfamilyfarm.com")
        self.assertIsNone(missing)

    def test_fallback_summary_stays_publication_only_and_serializable(self) -> None:
        summary = PublicationTenantSummary.fallback(
            tenant_id="fnd",
            tenant_domain="fruitfulnetworkdevelopment.com",
            warnings=("publication_unresolved",),
        )

        self.assertEqual(
            json.loads(json.dumps(summary.to_dict(), sort_keys=True)),
            {
                "tenant_id": "fnd",
                "tenant_domain": "fruitfulnetworkdevelopment.com",
                "profile_title": "Fnd",
                "profile_summary": "",
                "entity_type": "",
                "contact_email": "",
                "public_website_url": "",
                "available_documents": [],
                "profile_resolution": "publication_unresolved",
                "publication_mode": "publication-only",
                "warnings": ["publication_unresolved"],
            },
        )


if __name__ == "__main__":
    unittest.main()
