from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.fnd_dcm import (
    FndDcmReadOnlyService,
    normalize_board_profiles,
)
from MyCiteV2.packages.ports.fnd_dcm_read_only import (
    FndDcmReadOnlyResult,
    FndDcmReadOnlySource,
)


class _FakeFndDcmPort:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests = []

    def read_fnd_dcm_read_only(self, request):
        self.requests.append(request)
        return FndDcmReadOnlyResult(source=FndDcmReadOnlySource(payload=self.payload))


class FndDcmReadOnlyUnitTests(unittest.TestCase):
    def test_service_prefers_requested_site_and_clears_invalid_page_or_collection(self) -> None:
        payload = {
            "portal_tenant_id": "fnd",
            "profiles": [
                {
                    "domain": "cuyahogavalleycountrysideconservancy.org",
                    "label": "CVCC",
                    "manifest_schema": "webdz.site_content.v2",
                    "projection": {
                        "site": {"name": "CVCC", "schema": "webdz.site_content.v2"},
                        "navigation": [],
                        "footer": {"column_count": 1},
                        "pages": [{"id": "people", "file": "people.html", "template": "board_directory", "collection_refs": ["board_profiles"]}],
                        "collections": [
                            {
                                "id": "board_profiles",
                                "type": "json_file",
                                "source_count": 1,
                                "preview_payload": [
                                    {
                                        "name": "Jane Example",
                                        "alternative_email": "~",
                                        "contact_phone_number": "330-555-0100",
                                        "bio": ["Jane supports local farming."],
                                        "socials": [{"linkedin": "linkedin.com/in/jane-example"}],
                                        "tags": ["board_chair"],
                                    }
                                ],
                            }
                        ],
                        "issues": [],
                        "extensions": {},
                    },
                    "collection_sources": [
                        {
                            "collection_id": "board_profiles",
                            "source_kind": "json_file",
                            "relative_path": "assets/docs/board_profiles.json",
                            "exists": True,
                        }
                    ],
                    "normalization_evidence": ["Mapped v2 manifest."],
                    "raw_manifest": {"schema": "webdz.site_content.v2"},
                    "manifest_path": "/srv/webapps/clients/cuyahogavalleycountrysideconservancy.org/frontend/assets/docs/manifest.json",
                    "render_script_path": "/srv/webapps/clients/cuyahogavalleycountrysideconservancy.org/frontend/scripts/render_manifest.py",
                    "profile_file": "/srv/private/fnd-dcm.cvcc.json",
                    "issues": [],
                    "warnings": [],
                },
                {
                    "domain": "trappfamilyfarm.com",
                    "label": "Trapp Family Farm",
                    "manifest_schema": "webdz.site_content.v3",
                    "projection": {
                        "site": {"name": "Trapp Family Farm", "schema": "webdz.site_content.v3"},
                        "navigation": [],
                        "footer": {"column_count": 1},
                        "pages": [{"id": "home", "file": "home.html", "template": "home_featured", "collection_refs": []}],
                        "collections": [{"id": "newsletters", "type": "markdown_documents", "source_count": 1}],
                        "issues": [{"code": "manifest_warning", "message": "Example warning"}],
                        "extensions": {},
                    },
                    "collection_sources": [],
                    "normalization_evidence": ["Mapped v3 manifest."],
                    "raw_manifest": {"schema": "webdz.site_content.v3"},
                    "manifest_path": "/srv/webapps/clients/trappfamilyfarm.com/frontend/assets/docs/manifest.json",
                    "render_script_path": "/srv/webapps/clients/trappfamilyfarm.com/frontend/scripts/render_manifest.py",
                    "profile_file": "/srv/private/fnd-dcm.tff.json",
                    "issues": [],
                    "warnings": [],
                },
            ],
            "warnings": ["shared warning"],
        }
        service = FndDcmReadOnlyService(_FakeFndDcmPort(payload))

        page_selection = service.read_surface(
            portal_tenant_id="fnd",
            site="cuyahogavalleycountrysideconservancy.org",
            view="pages",
            page="people",
        )
        invalid_selection = service.read_surface(
            portal_tenant_id="fnd",
            site="trappfamilyfarm.com",
            view="pages",
            page="people",
            collection="board_profiles",
        )
        collection_selection = service.read_surface(
            portal_tenant_id="fnd",
            site="cuyahogavalleycountrysideconservancy.org",
            view="collections",
            collection="board_profiles",
        )

        self.assertEqual(page_selection["canonical_query"], {"site": "cuyahogavalleycountrysideconservancy.org", "view": "pages", "page": "people"})
        self.assertEqual(invalid_selection["canonical_query"], {"site": "trappfamilyfarm.com", "view": "pages"})
        self.assertEqual(collection_selection["canonical_query"], {"site": "cuyahogavalleycountrysideconservancy.org", "view": "collections", "collection": "board_profiles"})
        self.assertEqual(collection_selection["board_profile_preview"]["count"], 1)
        self.assertIn("shared warning", collection_selection["warnings"])

    def test_board_profile_normalization_canonicalizes_alias_fields_and_socials(self) -> None:
        normalized = normalize_board_profiles(
            [
                {
                    "name": "Jane Example",
                    "alternative_email": "~",
                    "contact_phone_number": "330-555-0100",
                    "bio": ["Jane supports local farming.", "She helps with outreach."],
                    "socials": [{"linkedin": "linkedin.com/in/jane-example"}],
                    "tags": ["board_chair"],
                },
                {
                    "id": "john-example",
                    "name": "John Example",
                    "summary_bio": "Custom summary",
                    "bio": [],
                    "socials": [{"platform": "website", "value": "example.org"}],
                    "why_joined_board": "To help.",
                },
            ]
        )

        self.assertEqual(normalized[0]["id"], "jane-example")
        self.assertEqual(normalized[0]["summary_bio"], "Jane supports local farming.")
        self.assertEqual(normalized[0]["secondary_email"], None)
        self.assertEqual(normalized[0]["phone"], "330-555-0100")
        self.assertEqual(normalized[0]["socials"], [{"platform": "linkedin", "value": "linkedin.com/in/jane-example"}])
        self.assertEqual(normalized[0]["tags"], ["board_chair"])
        self.assertEqual(normalized[1]["id"], "john-example")
        self.assertEqual(normalized[1]["summary_bio"], "Custom summary")
        self.assertEqual(normalized[1]["why_joined_the_board"], "To help.")


if __name__ == "__main__":
    unittest.main()
