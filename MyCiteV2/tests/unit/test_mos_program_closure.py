from __future__ import annotations

import json
import re
import sqlite3
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import AuthoritativeDatumDocumentRequest


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class MosProgramClosureTests(unittest.TestCase):
    def test_fnd_authority_db_matches_closure_counts(self) -> None:
        db_file = REPO_ROOT / "deployed" / "fnd" / "private" / "mos_authority.sqlite3"
        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row
            queries = {
                "document_semantics_count": "SELECT COUNT(*) AS count FROM datum_document_semantics WHERE tenant_id = 'fnd'",
                "row_semantics_count": "SELECT COUNT(*) AS count FROM datum_row_semantics WHERE tenant_id = 'fnd'",
                "catalog_snapshots_count": "SELECT COUNT(*) AS count FROM authoritative_catalog_snapshots WHERE tenant_id = 'fnd'",
                "system_workbench_count": "SELECT COUNT(*) AS count FROM system_workbench_snapshots WHERE tenant_id = 'fnd'",
                "publication_summary_count": "SELECT COUNT(*) AS count FROM publication_summary_snapshots WHERE tenant_id = 'fnd'",
                "portal_authority_count": "SELECT COUNT(*) AS count FROM portal_authority_snapshots WHERE scope_id = 'fnd'",
                "directive_snapshot_count": "SELECT COUNT(*) AS count FROM directive_context_snapshots WHERE portal_instance_id = 'fnd'",
                "directive_event_count": "SELECT COUNT(*) AS count FROM directive_context_events WHERE portal_instance_id = 'fnd'",
            }
            counts = {name: int(connection.execute(query).fetchone()["count"]) for name, query in queries.items()}
            self.assertEqual(counts["document_semantics_count"], 409)
            self.assertEqual(counts["row_semantics_count"], 3133)
            self.assertEqual(counts["catalog_snapshots_count"], 1)
            self.assertEqual(counts["system_workbench_count"], 1)
            self.assertEqual(counts["publication_summary_count"], 1)
            self.assertEqual(counts["portal_authority_count"], 1)
            self.assertEqual(counts["directive_snapshot_count"], 0)
            self.assertEqual(counts["directive_event_count"], 0)
        finally:
            connection.close()

    def test_fnd_authority_db_matches_filesystem_authoritative_corpus(self) -> None:
        data_dir = REPO_ROOT / "deployed" / "fnd" / "data"
        db_file = REPO_ROOT / "deployed" / "fnd" / "private" / "mos_authority.sqlite3"

        filesystem_catalog = FilesystemSystemDatumStoreAdapter(data_dir).read_authoritative_datum_documents(
            AuthoritativeDatumDocumentRequest(tenant_id="fnd")
        )
        filesystem_counts = {
            document.document_id: int(document.row_count)
            for document in filesystem_catalog.documents
        }

        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row
            sql_counts = {
                row["document_id"]: int(row["row_count"])
                for row in connection.execute(
                    """
                    SELECT document_id, COUNT(*) AS row_count
                    FROM datum_row_semantics
                    WHERE tenant_id = 'fnd'
                    GROUP BY document_id
                    """
                )
            }

            self.assertEqual(filesystem_counts, sql_counts)

            filesystem_cts = {
                document_id: row_count
                for document_id, row_count in filesystem_counts.items()
                if document_id.startswith("sandbox:cts_gis:")
            }
            sql_cts = {
                document_id: row_count
                for document_id, row_count in sql_counts.items()
                if document_id.startswith("sandbox:cts_gis:")
            }

            self.assertEqual(filesystem_cts, sql_cts)
            self.assertEqual(len(filesystem_counts), 409)
            self.assertEqual(sum(filesystem_counts.values()), 3133)
            self.assertEqual(len(filesystem_cts), 406)
            self.assertEqual(sum(filesystem_cts.values()), 2233)
        finally:
            connection.close()

    def test_cts_gis_row_graph_integrity_is_clean_in_live_authority_db(self) -> None:
        db_file = REPO_ROOT / "deployed" / "fnd" / "private" / "mos_authority.sqlite3"
        connection = sqlite3.connect(db_file)
        try:
            connection.row_factory = sqlite3.Row

            row_addresses_by_document: dict[str, set[str]] = {}
            for row in connection.execute(
                """
                SELECT document_id, datum_address
                FROM datum_row_semantics
                WHERE tenant_id = 'fnd' AND document_id LIKE 'sandbox:cts_gis:%'
                """
            ):
                row_addresses_by_document.setdefault(row["document_id"], set()).add(row["datum_address"])

            total_rows = 0
            for row in connection.execute(
                """
                SELECT document_id, datum_address, semantic_hash, hyphae_hash, local_references_json, warnings_json
                FROM datum_row_semantics
                WHERE tenant_id = 'fnd' AND document_id LIKE 'sandbox:cts_gis:%'
                """
            ):
                total_rows += 1
                self.assertTrue(row["semantic_hash"], row["datum_address"])
                self.assertTrue(row["hyphae_hash"], row["datum_address"])
                warnings = json.loads(row["warnings_json"] or "[]")
                local_references = json.loads(row["local_references_json"] or "[]")
                self.assertEqual(warnings, [], row["datum_address"])
                known_rows = row_addresses_by_document[row["document_id"]]
                for reference in local_references:
                    self.assertIn(reference, known_rows, f"{row['document_id']}:{row['datum_address']} -> {reference}")

            self.assertEqual(len(row_addresses_by_document), 406)
            self.assertEqual(total_rows, 2233)
        finally:
            connection.close()

    def test_closure_checklist_covers_every_plan_and_report_artifact(self) -> None:
        checklist_path = REPO_ROOT / "docs" / "audits" / "reports" / "mos_program_closure_audit_checklist_2026-04-21.md"
        checklist_text = _read_text(checklist_path)
        entries: dict[str, tuple[str, str]] = {}
        for line in checklist_text.splitlines():
            if not line.startswith("| `docs/"):
                continue
            parts = [part.strip() for part in line.strip().strip("|").split("|")]
            if len(parts) != 4:
                continue
            path = parts[0].strip("`")
            entries[path] = (parts[1].strip("`"), parts[3])

        expected_paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for root in (REPO_ROOT / "docs" / "plans", REPO_ROOT / "docs" / "audits" / "reports")
            for path in root.iterdir()
            if path.is_file()
        }
        self.assertEqual(set(entries), expected_paths)

        for path, (classification, note) in entries.items():
            self.assertIn(classification, {"authoritative", "supporting-current", "historical-superseded"})
            if classification != "historical-superseded":
                continue
            full_path = REPO_ROOT / path
            has_marker = full_path.suffix == ".md" and (
                "Historical status:" in _read_text(full_path) or "Supersession Note" in _read_text(full_path)
            )
            self.assertTrue(has_marker or "immutable evidence" in note.lower(), path)

    def test_active_mos_docs_drop_outdated_legacy_authority_phrases(self) -> None:
        master_plan = _read_text(REPO_ROOT / "docs" / "plans" / "master_plan_mos.md")
        index_yaml = _read_text(REPO_ROOT / "docs" / "plans" / "master_plan_mos.index.yaml")
        legacy_report = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "mos_sql_only_authority_activation_and_legacy_retirement_2026-04-21.md"
        )

        self.assertNotIn("keep filesystem adapters available as compatibility projections", master_plan)
        self.assertNotIn("filesystem adapters remain available as compatibility projections", master_plan)
        self.assertNotIn("while filesystem projections remain available", index_yaml)
        self.assertNotIn("rollback-safe filesystem projections remain available", index_yaml)
        self.assertIn("non-authoritative", master_plan)
        self.assertIn("non-authoritative", index_yaml)
        self.assertIn("non-authoritative", legacy_report)

    def test_migrated_system_runtime_defaults_are_sql_only(self) -> None:
        shell_runtime = _read_text(REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_shell_runtime.py")
        workspace_runtime = _read_text(
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_system_workspace_runtime.py"
        )

        self.assertIn('authority_mode: str = "sql_primary"', shell_runtime)
        self.assertNotIn('authority_mode: str = "filesystem"', shell_runtime)
        self.assertNotIn('authority_mode: str = "shadow"', shell_runtime)
        self.assertIn('authority_mode: str = "sql_primary"', workspace_runtime)
        self.assertNotIn('authority_mode: str = "filesystem"', workspace_runtime)
        self.assertNotIn('authority_mode: str = "shadow"', workspace_runtime)

    def test_python_source_drops_obsolete_filesystem_and_shadow_authority_modes(self) -> None:
        pattern = re.compile(r"authority_mode\s*[:=][^#\n]*[\"'](?:filesystem|shadow)[\"']")
        for path in (REPO_ROOT / "MyCiteV2").rglob("*.py"):
            if path.name == "test_mos_program_closure.py":
                continue
            self.assertIsNone(pattern.search(_read_text(path)), path.relative_to(REPO_ROOT).as_posix())

    def test_obsolete_mvp_runtime_is_removed(self) -> None:
        self.assertFalse((REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "mvp_runtime.py").exists())


if __name__ == "__main__":
    unittest.main()
