from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.sql import SqlitePortalAuthorityAdapter
from MyCiteV2.scripts.migrate_fnd_repo_to_mos_sql import classify_data_path, run_migration


class MigrateFndRepoToMosSqlTests(unittest.TestCase):
    def test_classify_data_path_covers_expected_buckets(self) -> None:
        self.assertEqual(classify_data_path("system/anthology.json"), "authoritative_import")
        self.assertEqual(classify_data_path("sandbox/cts-gis/tool.abc.cts-gis.json"), "supporting_anchor_context")
        self.assertEqual(classify_data_path("payloads/cache/sc.example.json"), "derived_materialization")
        self.assertEqual(classify_data_path("payloads/sc.example.bin"), "explicit_exception")

    def test_run_migration_applies_sql_import_and_enables_workbench_ui(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "deployed" / "fnd" / "data"
            public_dir = root / "deployed" / "fnd" / "public"
            private_dir = root / "deployed" / "fnd" / "private"
            db_file = private_dir / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "payloads").mkdir(parents=True, exist_ok=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            private_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "6-2-3": [["6-3-3", "3-1-4", "fnd", "4-1-1", "3-2-3-17-77-2-6-3-1-6"], ["example.com"]],
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["root"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "payloads" / "cache" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "payloads" / "sc.example.bin").write_bytes(b"\x00")
            (data_dir / "system" / "system_log.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "tool.test.cts-gis.json").write_text("{}\n", encoding="utf-8")
            (public_dir / "3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"title": "example", "entity_type": "legal_entity"}) + "\n",
                encoding="utf-8",
            )
            (public_dir / "fnd-3-2-3-17-77-2-6-3-1-6.json").write_text(
                json.dumps({"summary": "Tenant-facing summary"}) + "\n",
                encoding="utf-8",
            )
            (private_dir / "config.json").write_text(
                json.dumps({"tool_exposure": {"cts_gis": {"enabled": True}}}) + "\n",
                encoding="utf-8",
            )

            report = run_migration(
                data_root=data_dir,
                portal_config_path=private_dir / "config.json",
                authority_db_file=db_file,
                tenant_id="fnd",
                tenant_domain="example.com",
                apply=True,
            )

            self.assertEqual(report["coverage_gate"]["status"], "passed")
            self.assertFalse(report["failures"])
            authority = SqlitePortalAuthorityAdapter(db_file).read_portal_authority(
                {"scope_id": "fnd", "known_tool_ids": ["cts_gis", "workbench_ui"]}
            )
            self.assertTrue(authority.found)
            self.assertTrue(authority.source.tool_exposure_policy["enabled_tools"]["workbench_ui"])


if __name__ == "__main__":
    unittest.main()
