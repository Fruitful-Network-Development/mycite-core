from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.packages.adapters.sql import SqlitePortalAuthorityAdapter, SqliteSystemDatumStoreAdapter


def _seed_sql_authority(*, data_dir: Path, public_dir: Path, db_file: Path) -> None:
    SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
        data_dir=data_dir,
        public_dir=public_dir,
        tenant_id="fnd",
        tenant_domain="fruitfulnetworkdevelopment.com",
    )
    SqlitePortalAuthorityAdapter(db_file).store_portal_authority(
        {
            "scope_id": "fnd",
            "capabilities": [
                "datum_recognition",
                "spatial_projection",
                "fnd_peripheral_routing",
                "hosted_site_manifest_visibility",
                "hosted_site_visibility",
            ],
            "tool_exposure_policy": {
                "known_tool_ids": ["aws_csm", "cts_gis", "fnd_dcm", "fnd_ebi", "workbench_ui"],
                "configured_tools": {
                    "aws_csm": True,
                    "cts_gis": True,
                    "fnd_dcm": True,
                    "fnd_ebi": True,
                    "workbench_ui": True,
                },
                "enabled_tools": {
                    "aws_csm": True,
                    "cts_gis": True,
                    "fnd_dcm": True,
                    "fnd_ebi": True,
                    "workbench_ui": True,
                },
                "policy_source": "test_seed",
            },
            "ownership_posture": "portal_instance",
        }
    )


class PortalShellSqlAuthorityTests(unittest.TestCase):
    def test_system_surface_requires_initialized_sql_authority(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.root",
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            self.assertEqual(envelope["surface_id"], "system.root")
            self.assertEqual(envelope["error"]["code"], "sql_portal_authority_missing")

    def test_sql_primary_mode_reads_seeded_system_workspace_shape(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "payloads" / "cache" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            _seed_sql_authority(data_dir=data_dir, public_dir=public_dir, db_file=db_file)

            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.root",
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            self.assertEqual(envelope["surface_id"], "system.root")
            self.assertIsNone(envelope["error"])
            self.assertEqual(
                envelope["surface_payload"]["workspace"]["readiness_status"]["authoritative_catalog"],
                "loaded",
            )

    def test_sql_primary_mode_uses_db_backed_capabilities_for_tool_posture(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "payloads" / "cache" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            _seed_sql_authority(data_dir=data_dir, public_dir=public_dir, db_file=db_file)

            SqlitePortalAuthorityAdapter(db_file).store_portal_authority(
                {
                    "scope_id": "fnd",
                    "capabilities": ["datum_recognition"],
                    "tool_exposure_policy": {
                        "configured_tools": {"fnd_ebi": True, "workbench_ui": True},
                        "enabled_tools": {"fnd_ebi": True, "workbench_ui": True},
                        "policy_source": "sql_override",
                    },
                    "ownership_posture": "portal_instance",
                }
            )
            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.root",
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )
            self.assertEqual(envelope["portal_scope"]["capabilities"], ["datum_recognition"])
            compatible_section = next(
                section
                for section in envelope["shell_composition"]["regions"]["inspector"]["sections"]
                if section["title"] == "Compatible tool surfaces"
            )
            fnd_ebi_row = next(row for row in compatible_section["rows"] if row["label"] == "FND-EBI")
            self.assertIn("fnd_peripheral_routing", fnd_ebi_row["detail"])


if __name__ == "__main__":
    unittest.main()
