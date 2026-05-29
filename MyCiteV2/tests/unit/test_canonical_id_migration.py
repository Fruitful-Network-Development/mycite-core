"""Phase F unit tests for the canonical document-id migration script."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql._sqlite import open_sqlite
from MyCiteV2.packages.core.document_naming import is_canonical_document_id
from MyCiteV2.scripts.migrate_to_canonical_document_ids import migrate

MSN_ID = "3-2-3-17-77-1-6-4-1-4"


class CanonicalIdMigrationTests(unittest.TestCase):
    def _seed_legacy_documents(self, db_file: Path) -> None:
        with open_sqlite(db_file) as connection:
            connection.executemany(
                "INSERT INTO datum_document_semantics ("
                "tenant_id, document_id, policy, version_hash, "
                "canonical_payload_json, updated_at_unix_ms"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("fnd", "system:anthology", "P", "a" * 64, "{}", 0),
                    ("fnd", "sandbox:cts_gis:tool.xx.cts-gis.json", "P", "b" * 64, "{}", 0),
                    ("fnd", "sandbox:cts_gis:sc.example.precincts.json", "P", "c" * 64, "{}", 0),
                ],
            )
            connection.commit()

    def test_migration_produces_canonical_documents(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "auth.sqlite3"
            self._seed_legacy_documents(db_file)
            summary = migrate(db_file=db_file, msn_id=MSN_ID)
            self.assertEqual(summary["rows_seen"], 3)
            self.assertEqual(summary["rows_inserted"], 3)
            self.assertEqual(summary["rows_already_canonical"], 0)
            self.assertEqual(summary["rows_unsupported"], [])
            with open_sqlite(db_file) as connection:
                rows = list(
                    connection.execute(
                        "SELECT document_id, prefix, sandbox, name "
                        "FROM documents ORDER BY document_id"
                    )
                )
            self.assertEqual(len(rows), 3)
            # legacy_alias retired 2026-05-27: migration writes canonical ids only.
            for row in rows:
                self.assertTrue(is_canonical_document_id(row["document_id"]))
                self.assertEqual(row["prefix"], "lv")

    def test_migration_is_idempotent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "auth.sqlite3"
            self._seed_legacy_documents(db_file)
            first = migrate(db_file=db_file, msn_id=MSN_ID)
            self.assertEqual(first["rows_inserted"], 3)
            second = migrate(db_file=db_file, msn_id=MSN_ID)
            self.assertEqual(second["rows_seen"], 3)
            self.assertEqual(second["rows_inserted"], 0)
            self.assertEqual(second["rows_replaced"], 0)

    # test_repair_quarantines_malformed_sc_stems removed 2026-05-27: repair() re-derived
    # canonical ids from documents.legacy_alias, which is retired. The malformed-stem
    # quarantine path no longer has a legacy-alias source.


if __name__ == "__main__":
    unittest.main()
