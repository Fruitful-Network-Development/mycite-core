from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    PublicationProfileBasicsWritePort,
    PublicationProfileBasicsWriteRequest,
    PublicationTenantSummaryPort,
    PublicationTenantSummaryRequest,
)


class FilesystemPublicationTenantSummaryAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_publication_summary_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemSystemDatumStoreAdapter(Path(temp_dir), public_dir=Path(temp_dir))
            self.assertIsInstance(adapter, PublicationTenantSummaryPort)
            self.assertIsInstance(adapter, PublicationProfileBasicsWritePort)

    def test_reads_publication_profiles_through_domain_row_mapping(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "6-2-3": [
                            ["6-3-3", "3-1-4", "f7472617070", "4-1-1", "3-2-3-17-77-2-6-3-1-6"],
                            ["trappfamilyfarm.com"],
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"title": "trapp_family_farm", "entity_type": "legal_entity"}) + "\n",
                encoding="utf-8",
            )
            (public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"summary": "Tenant-facing summary"}) + "\n",
                encoding="utf-8",
            )

            result = FilesystemSystemDatumStoreAdapter(data_dir, public_dir=public_dir).read_publication_tenant_summary(
                PublicationTenantSummaryRequest(
                    tenant_id="tff",
                    tenant_domain="trappfamilyfarm.com",
                )
            )

            payload = result.to_dict()
            self.assertTrue(payload["found"])
            self.assertEqual(payload["source"]["profile_id"], "3-2-3-17-77-2-6-3-1-6")
            self.assertEqual(payload["resolution_status"]["anthology"], "loaded")
            self.assertEqual(payload["resolution_status"]["domain_match"], "matched")
            self.assertEqual(payload["resolution_status"]["public_profile"], "loaded")
            self.assertEqual(payload["resolution_status"]["tenant_profile"], "loaded")

    def test_missing_domain_mapping_returns_unfound_result_with_warning(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(json.dumps({}) + "\n", encoding="utf-8")

            result = FilesystemSystemDatumStoreAdapter(data_dir).read_publication_tenant_summary(
                {"tenant_id": "tff", "tenant_domain": "trappfamilyfarm.com"}
            )

            payload = result.to_dict()
            self.assertFalse(payload["found"])
            self.assertEqual(payload["resolution_status"]["anthology"], "loaded")
            self.assertEqual(payload["resolution_status"]["domain_match"], "missing")
            self.assertIn("No canonical publication profile mapping", " ".join(payload["warnings"]))

    def test_write_updates_only_bounded_profile_fields_and_reads_back(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "6-2-3": [
                            ["6-3-3", "3-1-4", "f7472617070", "4-1-1", "3-2-3-17-77-2-6-3-1-6"],
                            ["trappfamilyfarm.com"],
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"title": "trapp_family_farm", "entity_type": "legal_entity"}) + "\n",
                encoding="utf-8",
            )
            tenant_profile_path = public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json"
            tenant_profile_path.write_text(
                json.dumps(
                    {
                        "summary": "Old summary",
                        "logo": "",
                        "custom_flag": "keep-me",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            adapter = FilesystemSystemDatumStoreAdapter(data_dir, public_dir=public_dir)
            result = adapter.write_publication_profile_basics(
                PublicationProfileBasicsWriteRequest(
                    tenant_id="tff",
                    tenant_domain="trappfamilyfarm.com",
                    profile_title="Trapp Family Farm",
                    profile_summary="Updated summary",
                    contact_email="hello@trappfamilyfarm.com",
                    public_website_url="https://trappfamilyfarm.com",
                )
            )

            payload = result.to_dict()
            self.assertEqual(payload["source"]["profile_id"], "3-2-3-17-77-2-6-3-1-6")
            self.assertEqual(payload["source"]["tenant_profile"]["title"], "Trapp Family Farm")
            self.assertEqual(payload["source"]["tenant_profile"]["summary"], "Updated summary")
            self.assertEqual(
                payload["source"]["tenant_profile"]["contact_email"],
                "hello@trappfamilyfarm.com",
            )
            self.assertEqual(
                payload["source"]["tenant_profile"]["public_website_url"],
                "https://trappfamilyfarm.com",
            )
            written_payload = json.loads(tenant_profile_path.read_text(encoding="utf-8"))
            self.assertEqual(written_payload["custom_flag"], "keep-me")
            self.assertEqual(written_payload["title"], "Trapp Family Farm")
            self.assertEqual(written_payload["summary"], "Updated summary")

    def test_write_creates_missing_tenant_profile_document(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "6-2-3": [
                            ["6-3-3", "3-1-4", "f7472617070", "4-1-1", "3-2-3-17-77-2-6-3-1-6"],
                            ["trappfamilyfarm.com"],
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"title": "trapp_family_farm", "entity_type": "legal_entity"}) + "\n",
                encoding="utf-8",
            )

            adapter = FilesystemSystemDatumStoreAdapter(data_dir, public_dir=public_dir)
            adapter.write_publication_profile_basics(
                {
                    "tenant_id": "tff",
                    "tenant_domain": "trappfamilyfarm.com",
                    "profile_title": "Trapp Family Farm",
                    "profile_summary": "",
                    "contact_email": "",
                    "public_website_url": "",
                }
            )

            written_payload = json.loads(
                (public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json").read_text(encoding="utf-8")
            )
            self.assertEqual(written_payload["title"], "Trapp Family Farm")
            self.assertEqual(written_payload["summary"], "")

    def test_write_rejects_invalid_existing_tenant_profile_without_mutating(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "6-2-3": [
                            ["6-3-3", "3-1-4", "f7472617070", "4-1-1", "3-2-3-17-77-2-6-3-1-6"],
                            ["trappfamilyfarm.com"],
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"title": "trapp_family_farm"}) + "\n",
                encoding="utf-8",
            )
            tenant_profile_path = public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json"
            tenant_profile_path.write_text("{bad-json\n", encoding="utf-8")

            adapter = FilesystemSystemDatumStoreAdapter(data_dir, public_dir=public_dir)
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                adapter.write_publication_profile_basics(
                    {
                        "tenant_id": "tff",
                        "tenant_domain": "trappfamilyfarm.com",
                        "profile_title": "Trapp Family Farm",
                        "profile_summary": "Updated summary",
                        "contact_email": "hello@trappfamilyfarm.com",
                        "public_website_url": "https://trappfamilyfarm.com",
                    }
                )

            self.assertEqual(tenant_profile_path.read_text(encoding="utf-8"), "{bad-json\n")


if __name__ == "__main__":
    unittest.main()
