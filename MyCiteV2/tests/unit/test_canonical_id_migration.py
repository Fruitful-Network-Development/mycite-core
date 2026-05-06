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
from MyCiteV2.scripts.migrate_to_canonical_document_ids import migrate, repair

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

    def test_migration_produces_canonical_documents_with_legacy_alias(self) -> None:
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
                        "SELECT document_id, prefix, sandbox, name, legacy_alias "
                        "FROM documents ORDER BY document_id"
                    )
                )
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertTrue(is_canonical_document_id(row["document_id"]))
                self.assertEqual(row["prefix"], "lv")
                self.assertTrue(row["legacy_alias"])

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

    def test_repair_quarantines_malformed_sc_stems(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "auth.sqlite3"
            quarantine_log = Path(temp_dir) / "quarantine.ndjson"
            with open_sqlite(db_file) as connection:
                connection.executemany(
                    "INSERT INTO documents ("
                    "tenant_id, document_id, prefix, msn_id, sandbox, name, "
                    "version_hash, is_anchor, origin, legacy_alias, created_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            "fnd",
                            f"lv.{MSN_ID}.cts-gis.sc.{'d' * 64}",
                            "lv",
                            MSN_ID,
                            "cts-gis",
                            "sc",
                            "d" * 64,
                            0,
                            "local",
                            f"sandbox:cts_gis:sc.{MSN_ID}.msn-.json",
                            0,
                        ),
                        (
                            "fnd",
                            f"lv.{MSN_ID}.cts-gis.sc_empty.{'e' * 64}",
                            "lv",
                            MSN_ID,
                            "cts-gis",
                            "sc",
                            "e" * 64,
                            0,
                            "local",
                            f"sandbox:cts_gis:sc.{MSN_ID}..json",
                            0,
                        ),
                    ],
                )
                connection.commit()

            summary = repair(
                db_file=db_file,
                msn_id=MSN_ID,
                quarantine_log=quarantine_log,
            )

            self.assertEqual(summary["rows_quarantined"], 2)
            self.assertEqual(summary["rows_repaired"], 0)
            self.assertTrue(quarantine_log.exists())
            lines = [line for line in quarantine_log.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            self.assertIn(f"sc.{MSN_ID}.msn-.json", lines[0] + lines[1])
            self.assertIn(f"sc.{MSN_ID}..json", lines[0] + lines[1])


if __name__ == "__main__":
    unittest.main()
