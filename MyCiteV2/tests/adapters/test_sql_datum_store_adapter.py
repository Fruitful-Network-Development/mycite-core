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
from MyCiteV2.packages.adapters.sql import SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocumentRequest,
    PublicationTenantSummaryRequest,
    SystemDatumStoreRequest,
)


class SqlDatumStoreAdapterTests(unittest.TestCase):
    def test_bootstrap_from_filesystem_preserves_catalog_and_workbench_shapes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "payloads" / "cache" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                json.dumps({"3-1-3": [["3-1-3", "2-1-1", "0"], ["canonical-anchor"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"4-2-1": [["4-2-1", "rf.3-1-3", "HERE"], ["row"]]}) + "\n",
                encoding="utf-8",
            )

            filesystem = FilesystemSystemDatumStoreAdapter(data_dir, public_dir=public_dir)
            expected_catalog = filesystem.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            ).to_dict()
            expected_workbench = filesystem.read_system_resource_workbench(
                SystemDatumStoreRequest(tenant_id="fnd")
            ).to_dict()

            sql_adapter = SqliteSystemDatumStoreAdapter(db_file)
            sql_adapter.bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            self.assertEqual(
                sql_adapter.read_authoritative_datum_documents(
                    AuthoritativeDatumDocumentRequest(tenant_id="fnd")
                ).to_dict(),
                expected_catalog,
            )
            self.assertEqual(
                sql_adapter.read_system_resource_workbench(SystemDatumStoreRequest(tenant_id="fnd")).to_dict(),
                expected_workbench,
            )

    def test_publication_summary_round_trip_and_write_stay_in_sql(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "1-0-1": [["1-0-1", "~", "0-0-0", "labels", "example.com", "profile-a"], ["example.com"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (public_dir / "profile-a.json").write_text(json.dumps({"title": "Public"}) + "\n", encoding="utf-8")
            (public_dir / "fnd-profile-a.json").write_text(json.dumps({"title": "Tenant"}) + "\n", encoding="utf-8")

            sql_adapter = SqliteSystemDatumStoreAdapter(db_file)
            sql_adapter.bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
                tenant_domain="example.com",
            )
            before = sql_adapter.read_publication_tenant_summary(
                PublicationTenantSummaryRequest(tenant_id="fnd", tenant_domain="example.com")
            )
            self.assertTrue(before.found)

            after = sql_adapter.write_publication_profile_basics(
                {
                    "tenant_id": "fnd",
                    "tenant_domain": "example.com",
                    "profile_title": "Updated Title",
                    "profile_summary": "Updated Summary",
                    "contact_email": "hello@example.com",
                    "public_website_url": "https://example.com",
                }
            )
            self.assertEqual(after.source.tenant_profile["title"], "Updated Title")
            self.assertEqual(after.source.tenant_profile["summary"], "Updated Summary")


if __name__ == "__main__":
    unittest.main()
