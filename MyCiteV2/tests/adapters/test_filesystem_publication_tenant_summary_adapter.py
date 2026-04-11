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
    PublicationTenantSummaryPort,
    PublicationTenantSummaryRequest,
)


class FilesystemPublicationTenantSummaryAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_publication_summary_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemSystemDatumStoreAdapter(Path(temp_dir), public_dir=Path(temp_dir))
            self.assertIsInstance(adapter, PublicationTenantSummaryPort)

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


if __name__ == "__main__":
    unittest.main()
