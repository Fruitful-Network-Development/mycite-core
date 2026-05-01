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
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRequest,
    AuthoritativeDatumDocumentRow,
    PublicationTenantSummaryRequest,
    SystemDatumStoreRequest,
)


class SqlDatumStoreAdapterTests(unittest.TestCase):
    def _seed_catalog(
        self,
        adapter: SqliteSystemDatumStoreAdapter,
        *,
        rows: tuple[tuple[str, object], ...],
        tenant_id: str = "fnd",
        document_id: str = "system:anthology",
    ) -> None:
        adapter.store_authoritative_catalog(
            AuthoritativeDatumDocumentCatalogResult(
                tenant_id=tenant_id,
                documents=(
                    AuthoritativeDatumDocument(
                        document_id=document_id,
                        source_kind="system_anthology",
                        document_name="anthology.json",
                        relative_path="system/anthology.json",
                        document_metadata={"semantic_mode": "test"},
                        rows=tuple(
                            AuthoritativeDatumDocumentRow(datum_address=datum_address, raw=raw)
                            for datum_address, raw in rows
                        ),
                    ),
                ),
                source_files={"system_anthology": "system/anthology.json"},
                readiness_status={"authoritative_catalog": "loaded"},
            )
        )

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

    def test_store_authoritative_catalog_persists_version_identity_and_hyphae_chain(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("0-0-1", [["0-0-1", "~", "ROOT"], ["rudi-1"]]),
                    ("0-0-2", [["0-0-2", "~", "0-0-1"], ["rudi-2"]]),
                    ("0-0-3", [["0-0-3", "~", "0-0-2"], ["rudi-3"]]),
                    ("1-0-1", [["1-0-1", "~", "0-0-3"], ["derived-1"]]),
                    ("2-0-1", [["2-0-1", "~", "1-0-1"], ["derived-2"]]),
                ),
            )

            document_identity = adapter.read_document_version_identity(
                tenant_id="fnd",
                document_id="system:anthology",
            )
            self.assertIsNotNone(document_identity)
            self.assertEqual(document_identity["policy"], "mos.mss_sha256_v1")
            self.assertTrue(document_identity["version_hash"].startswith("sha256:"))
            self.assertEqual(len(document_identity["canonical_payload"]["rows"]), 5)

            datum_identity = adapter.read_datum_semantic_identity(
                tenant_id="fnd",
                document_id="system:anthology",
                datum_address="2-0-1",
            )
            self.assertIsNotNone(datum_identity)
            self.assertEqual(datum_identity["policy"], "mos.hyphae_chain_v1")
            self.assertEqual(
                datum_identity["hyphae_chain"]["addresses"],
                ["0-0-1", "0-0-2", "0-0-3", "1-0-1", "2-0-1"],
            )
            self.assertEqual(datum_identity["local_references"], ["1-0-1"])

    def test_apply_document_insert_shifts_rows_and_updates_references(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("1-0-1", [["1-0-1", "~", "ROOT"], ["first"]]),
                    ("1-0-2", [["1-0-2", "~", "1-0-1"], ["second"]]),
                    ("1-0-3", [["1-0-3", "~", "1-0-2"], ["third"]]),
                    ("2-0-1", [["2-0-1", "~", "1-0-2"], ["consumer"]]),
                ),
            )

            result = adapter.apply_document_insert(
                tenant_id="fnd",
                document_id="system:anthology",
                target_address="1-0-2",
                raw=[["1-0-2", "~", "1-0-2"], ["inserted"]],
            )

            updated_rows = result["updated_document"]["documents"][0]["rows"] if "documents" in result["updated_document"] else result["updated_document"]["rows"]
            addresses = [row["datum_address"] for row in updated_rows]
            self.assertEqual(addresses, ["1-0-1", "1-0-2", "1-0-3", "1-0-4", "2-0-1"])
            self.assertEqual(updated_rows[1]["raw"][0][2], "1-0-3")
            self.assertEqual(updated_rows[2]["raw"][0][0], "1-0-3")
            self.assertEqual(updated_rows[4]["raw"][0][2], "1-0-3")
            self.assertEqual(result["persisted_version_hash"], result["version_hash_after"])

    def test_apply_document_insert_remaps_hyphen_qualified_refs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("4-2-1", [["4-2-1", "rf.3-1-2", "3-2-3-17-18-1-1-1-1", "rf.3-1-3", "BITS"], ["first"]]),
                    ("4-2-2", [["4-2-2", "rf.3-1-2", "3-2-3-17-18-1-1-2-1", "rf.3-1-3", "BITS", "3-2-3-17-28-3-4-2-1"], ["qualified_ref"]]),
                ),
            )

            result = adapter.apply_document_insert(
                tenant_id="fnd",
                document_id="system:anthology",
                target_address="4-2-1",
                raw=[["4-2-1", "rf.3-1-2", "3-2-3-17-77-1-6-999-2", "rf.3-1-3", "BITS"], ["inserted"]],
            )

            updated_rows = result["updated_document"]["rows"]
            qualified_row = next(row for row in updated_rows if row["datum_address"] == "4-2-3")
            self.assertIn("3-2-3-17-28-3-4-2-2", qualified_row["raw"][0])
            self.assertEqual(result["persisted_version_hash"], result["version_hash_after"])

    def test_apply_document_insert_allows_append_on_sparse_family(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("1-0-1", [["1-0-1", "~", "ROOT"], ["first"]]),
                    ("1-0-3", [["1-0-3", "~", "1-0-1"], ["third"]]),
                    ("1-0-5", [["1-0-5", "~", "1-0-3"], ["fifth"]]),
                ),
            )

            result = adapter.apply_document_insert(
                tenant_id="fnd",
                document_id="system:anthology",
                target_address="1-0-6",
                raw=[["1-0-6", "~", "1-0-5"], ["sixth"]],
            )

            updated_rows = result["updated_document"]["rows"]
            addresses = [row["datum_address"] for row in updated_rows]
            self.assertEqual(addresses, ["1-0-1", "1-0-3", "1-0-5", "1-0-6"])
            self.assertEqual(updated_rows[-1]["raw"][0][2], "1-0-5")
            self.assertEqual(result["persisted_version_hash"], result["version_hash_after"])

    def test_apply_document_delete_rejects_live_references(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("1-0-1", [["1-0-1", "~", "ROOT"], ["first"]]),
                    ("1-0-2", [["1-0-2", "~", "1-0-1"], ["second"]]),
                    ("1-0-3", [["1-0-3", "~", "1-0-2"], ["third"]]),
                ),
            )

            with self.assertRaisesRegex(ValueError, "delete_target_row_still_referenced"):
                adapter.preview_document_delete(
                    tenant_id="fnd",
                    document_id="system:anthology",
                    target_address="1-0-2",
                )

    def test_apply_document_delete_shifts_following_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("1-0-1", [["1-0-1", "~", "ROOT"], ["first"]]),
                    ("1-0-2", [["1-0-2", "~", "1-0-1"], ["second"]]),
                    ("1-0-3", [["1-0-3", "~", "1-0-1"], ["third"]]),
                    ("2-0-1", [["2-0-1", "~", "1-0-3"], ["consumer"]]),
                ),
            )

            result = adapter.apply_document_delete(
                tenant_id="fnd",
                document_id="system:anthology",
                target_address="1-0-2",
            )

            updated_rows = result["updated_document"]["rows"]
            addresses = [row["datum_address"] for row in updated_rows]
            self.assertEqual(addresses, ["1-0-1", "1-0-2", "2-0-1"])
            self.assertEqual(updated_rows[1]["raw"][0][0], "1-0-2")
            self.assertEqual(updated_rows[2]["raw"][0][2], "1-0-2")
            self.assertEqual(result["persisted_version_hash"], result["version_hash_after"])

    def test_apply_document_move_reindexes_source_and_destination_families(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = SqliteSystemDatumStoreAdapter(Path(temp_dir) / "authority.sqlite3")
            self._seed_catalog(
                adapter,
                rows=(
                    ("1-0-1", [["1-0-1", "~", "ROOT"], ["first"]]),
                    ("1-0-2", [["1-0-2", "~", "1-0-1"], ["second"]]),
                    ("1-0-3", [["1-0-3", "~", "1-0-2"], ["third"]]),
                    ("2-0-1", [["2-0-1", "~", "1-0-1"], ["consumer"]]),
                ),
            )

            result = adapter.apply_document_move(
                tenant_id="fnd",
                document_id="system:anthology",
                source_address="1-0-1",
                destination_address="1-0-3",
            )

            updated_rows = result["updated_document"]["rows"]
            addresses = [row["datum_address"] for row in updated_rows]
            self.assertEqual(addresses, ["1-0-1", "1-0-2", "1-0-3", "2-0-1"])
            self.assertEqual(updated_rows[0]["raw"][0][2], "1-0-3")
            self.assertEqual(updated_rows[1]["raw"][0][2], "1-0-1")
            self.assertEqual(updated_rows[2]["raw"][0][0], "1-0-3")
            self.assertEqual(updated_rows[3]["raw"][0][2], "1-0-3")
            self.assertEqual(result["persisted_version_hash"], result["version_hash_after"])


if __name__ == "__main__":
    unittest.main()
