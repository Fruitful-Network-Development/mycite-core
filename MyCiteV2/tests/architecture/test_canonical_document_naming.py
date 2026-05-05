"""Architecture tests asserting the canonical document-naming surface area.

Phase F gate for the Three-Panel Portal Convergence:

* every row in the ``documents`` table (after migration) matches the canonical
  ``lv|stl|cptr.<msn>(.<sandbox>).<name>.<hash>`` regex
* the ``datum_document_semantics`` table accepts both canonical and legacy
  identifiers during the one-cycle compatibility window
* the SQL adapter is wired to the migration helpers
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql._sqlite import open_sqlite
from MyCiteV2.packages.adapters.sql.datum_store import (
    NonCanonicalDocumentIdError,
    SqliteSystemDatumStoreAdapter,
)
from MyCiteV2.packages.core.document_naming import is_canonical_document_id
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
)
from MyCiteV2.scripts.migrate_to_canonical_document_ids import migrate

CANONICAL_REGEX = re.compile(
    r"^(lv|stl|cptr)\.[^.]+(\.[^.]+)?\.[^.]+\.[a-f0-9]{64}$"
)


class CanonicalDocumentNamingArchitectureTests(unittest.TestCase):
    def test_documents_table_rows_are_all_canonical_after_migration(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "auth.sqlite3"
            with open_sqlite(db_file) as connection:
                connection.executemany(
                    "INSERT INTO datum_document_semantics ("
                    "tenant_id, document_id, policy, version_hash, "
                    "canonical_payload_json, updated_at_unix_ms"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        ("fnd", "system:anthology", "P", "a" * 64, "{}", 0),
                        ("fnd", "sandbox:cts_gis:tool.xx.cts-gis.json", "P", "b" * 64, "{}", 0),
                    ],
                )
                connection.commit()
            migrate(db_file=db_file, msn_id="3-2-3-17-77-1-6-4-1-4")
            with open_sqlite(db_file) as connection:
                document_ids = [
                    str(row["document_id"]).strip()
                    for row in connection.execute("SELECT document_id FROM documents")
                ]
            self.assertTrue(document_ids)
            for doc_id in document_ids:
                self.assertRegex(doc_id, CANONICAL_REGEX)
                self.assertTrue(is_canonical_document_id(doc_id))

    def test_datum_store_accepts_both_canonical_and_legacy_lookups(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "auth.sqlite3"
            store = SqliteSystemDatumStoreAdapter(db_file)
            doc = AuthoritativeDatumDocument(
                document_id="system:anthology",
                document_name="anthology",
                relative_path="anthology.json",
                source_kind="system_anthology",
            )
            store.store_authoritative_catalog(
                AuthoritativeDatumDocumentCatalogResult(
                    tenant_id="fnd",
                    documents=(doc,),
                    source_files={},
                    readiness_status={},
                    warnings=(),
                )
            )
            migrate(db_file=db_file, msn_id="3-2-3-17-77-1-6-4-1-4")
            legacy_hit = store.read_document_version_identity(
                tenant_id="fnd", document_id="system:anthology"
            )
            self.assertIsNotNone(legacy_hit)
            with open_sqlite(db_file) as connection:
                canonical_id = str(
                    connection.execute(
                        "SELECT document_id FROM documents WHERE legacy_alias = ?",
                        ("system:anthology",),
                    ).fetchone()["document_id"]
                ).strip()
            canonical_hit = store.read_document_version_identity(
                tenant_id="fnd", document_id=canonical_id
            )
            self.assertIsNotNone(canonical_hit)

    def test_strict_mode_rejects_non_canonical_writes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "auth.sqlite3"
            store = SqliteSystemDatumStoreAdapter(db_file, allow_legacy_writes=False)
            doc = AuthoritativeDatumDocument(
                document_id="system:anthology",
                document_name="anthology",
                relative_path="anthology.json",
                source_kind="system_anthology",
            )
            with self.assertRaises(NonCanonicalDocumentIdError):
                store.store_authoritative_catalog(
                    AuthoritativeDatumDocumentCatalogResult(
                        tenant_id="fnd",
                        documents=(doc,),
                        source_files={},
                        readiness_status={},
                        warnings=(),
                    )
                )


if __name__ == "__main__":
    unittest.main()
