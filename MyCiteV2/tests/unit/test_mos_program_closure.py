from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class MosProgramClosureTests(unittest.TestCase):
    def test_fnd_authority_db_matches_closure_counts(self) -> None:
        db_file = REPO_ROOT / "deployed" / "fnd" / "private" / "mos_authority.sqlite3"
        connection = sqlite3.connect(db_file)
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
        self.assertIn('authority_mode: str = "sql_primary"', workspace_runtime)
        self.assertNotIn('authority_mode: str = "filesystem"', workspace_runtime)


if __name__ == "__main__":
    unittest.main()
