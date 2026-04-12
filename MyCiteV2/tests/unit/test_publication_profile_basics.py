from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.domains.publication import (
    PublicationProfileBasicsService,
    normalize_publication_profile_basics_command,
)
from MyCiteV2.packages.ports.datum_store import PublicationProfileBasicsWriteResult


class _FakePublicationProfileBasicsPort:
    def __init__(self) -> None:
        self.requests = []
        self.result = PublicationProfileBasicsWriteResult(
            source={
                "tenant_id": "tff",
                "tenant_domain": "trappfamilyfarm.com",
                "profile_id": "3-2-3-17-77-2-6-3-1-6",
                "public_profile": {
                    "title": "trapp_family_farm",
                    "entity_type": "legal_entity",
                },
                "tenant_profile": {
                    "title": "Trapp Family Farm",
                    "summary": "Updated summary",
                    "contact_email": "hello@trappfamilyfarm.com",
                    "public_website_url": "https://trappfamilyfarm.com",
                },
            },
            resolution_status={
                "anthology": "loaded",
                "domain_match": "matched",
                "public_profile": "loaded",
                "tenant_profile": "loaded",
            },
        )

    def write_publication_profile_basics(self, request):
        self.requests.append(request)
        return self.result


class PublicationProfileBasicsUnitTests(unittest.TestCase):
    def test_command_normalizes_and_rejects_invalid_optional_fields(self) -> None:
        command = normalize_publication_profile_basics_command(
            {
                "tenant_id": "TFF",
                "tenant_domain": "TrappFamilyFarm.com",
                "profile_title": "Trapp Family Farm",
                "profile_summary": " Updated summary ",
                "contact_email": "HELLO@TRAPPFAMILYFARM.COM",
                "public_website_url": "https://trappfamilyfarm.com",
            }
        )

        self.assertEqual(
            command.to_dict(),
            {
                "tenant_id": "tff",
                "tenant_domain": "trappfamilyfarm.com",
                "profile_title": "Trapp Family Farm",
                "profile_summary": "Updated summary",
                "contact_email": "hello@trappfamilyfarm.com",
                "public_website_url": "https://trappfamilyfarm.com",
                "writable_field_set": [
                    "profile_title",
                    "profile_summary",
                    "contact_email",
                    "public_website_url",
                ],
            },
        )

        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            normalize_publication_profile_basics_command(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "Trapp Family Farm",
                    "unknown": "nope",
                }
            )

        with self.assertRaisesRegex(ValueError, "email-like"):
            normalize_publication_profile_basics_command(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "Trapp Family Farm",
                    "contact_email": "bad-email",
                }
            )

        with self.assertRaisesRegex(ValueError, "http\\(s\\) URL"):
            normalize_publication_profile_basics_command(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "Trapp Family Farm",
                    "public_website_url": "ftp://example.com",
                }
            )

    def test_service_applies_write_and_prepares_local_audit_payload(self) -> None:
        port = _FakePublicationProfileBasicsPort()
        service = PublicationProfileBasicsService(port)

        outcome = service.apply_write(
            {
                "tenant_id": "tff",
                "tenant_domain": "trappfamilyfarm.com",
                "profile_title": "Trapp Family Farm",
                "profile_summary": "Updated summary",
                "contact_email": "hello@trappfamilyfarm.com",
                "public_website_url": "https://trappfamilyfarm.com",
            }
        )

        self.assertEqual(port.requests[0].tenant_domain, "trappfamilyfarm.com")
        self.assertEqual(outcome.profile_id, "3-2-3-17-77-2-6-3-1-6")
        self.assertEqual(outcome.confirmed_summary.profile_title, "Trapp Family Farm")
        self.assertEqual(
            outcome.to_local_audit_payload(),
            {
                "event_type": "publication.profile_basics.write.accepted",
                "focus_subject": "3-2-3-17-77-2-6-3-1-6.4-1-1",
                "shell_verb": "portal.profile_basics_write",
                "details": {
                    "tenant_scope_id": "tff",
                    "profile_id": "3-2-3-17-77-2-6-3-1-6",
                    "updated_fields": [
                        "profile_title",
                        "profile_summary",
                        "contact_email",
                        "public_website_url",
                    ],
                    "profile_title": "Trapp Family Farm",
                    "profile_summary": "Updated summary",
                    "contact_email": "hello@trappfamilyfarm.com",
                    "public_website_url": "https://trappfamilyfarm.com",
                },
            },
        )

    def test_service_rejects_confirmation_mismatch(self) -> None:
        port = _FakePublicationProfileBasicsPort()
        port.result = PublicationProfileBasicsWriteResult(
            source={
                "tenant_id": "tff",
                "tenant_domain": "trappfamilyfarm.com",
                "profile_id": "3-2-3-17-77-2-6-3-1-6",
                "public_profile": {"title": "trapp_family_farm"},
                "tenant_profile": {
                    "title": "Trapp Family Farm",
                    "summary": "Updated summary",
                    "contact_email": "other@trappfamilyfarm.com",
                    "public_website_url": "https://trappfamilyfarm.com",
                },
            },
            resolution_status={
                "anthology": "loaded",
                "domain_match": "matched",
                "public_profile": "loaded",
                "tenant_profile": "loaded",
            },
        )

        with self.assertRaisesRegex(ValueError, "contact_email"):
            PublicationProfileBasicsService(port).apply_write(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "Trapp Family Farm",
                    "profile_summary": "Updated summary",
                    "contact_email": "hello@trappfamilyfarm.com",
                    "public_website_url": "https://trappfamilyfarm.com",
                }
            )


if __name__ == "__main__":
    unittest.main()
