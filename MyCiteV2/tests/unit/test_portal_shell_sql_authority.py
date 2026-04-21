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


class PortalShellSqlAuthorityTests(unittest.TestCase):
    def test_sql_primary_mode_bootstraps_and_preserves_system_workspace_shape(self) -> None:
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

            first = run_portal_shell_entry(
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
            self.assertIn("fnd_peripheral_routing", first["portal_scope"]["capabilities"])

            from MyCiteV2.packages.adapters.sql import SqlitePortalAuthorityAdapter

            SqlitePortalAuthorityAdapter(db_file).store_portal_authority(
                {
                    "scope_id": "fnd",
                    "capabilities": ["datum_recognition"],
                    "tool_exposure_policy": {
                        "configured_tools": {"fnd_ebi": True},
                        "enabled_tools": {"fnd_ebi": True},
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
