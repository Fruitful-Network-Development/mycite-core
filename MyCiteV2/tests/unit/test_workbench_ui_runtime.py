from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_workbench_ui_runtime import (
    build_portal_workbench_ui_surface_bundle,
    run_portal_workbench_ui,
)
from MyCiteV2.packages.adapters.sql import SqliteDirectiveContextAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.state_machine.portal_shell import PortalScope


class WorkbenchUiRuntimeTests(unittest.TestCase):
    def test_workbench_ui_runtime_reads_sql_rows_and_projects_grid(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["root"]],
                        "1-1-2": [["1-1-2", "1-1-1", "CHILD"], ["child"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            envelope = run_portal_workbench_ui(
                {
                    "schema": "mycite.v2.portal.system.tools.workbench_ui.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"document": "system:anthology", "sort": "hyphae_hash", "dir": "asc"},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                authority_db_file=db_file,
            )

            self.assertEqual(envelope["surface_id"], "system.tools.workbench_ui")
            self.assertEqual(envelope["canonical_query"]["sort"], "hyphae_hash")
            table = envelope["surface_payload"]["sections"][0]
            self.assertEqual(table["title"], "Datum Grid")
            self.assertEqual(len(table["items"]), 2)
            self.assertTrue(table["items"][0]["hyphae_hash"])

    def test_workbench_ui_overlay_remains_additive_and_does_not_mutate_rows(self) -> None:
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
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["root"]],
                        "1-1-2": [["1-1-2", "1-1-1", "CHILD"], ["child"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            datum_store = SqliteSystemDatumStoreAdapter(db_file)
            datum_store.bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )
            document_identity = datum_store.read_document_version_identity(
                tenant_id="fnd",
                document_id="system:anthology",
            )
            row_identity = datum_store.read_datum_semantic_identity(
                tenant_id="fnd",
                document_id="system:anthology",
                datum_address="1-1-2",
            )
            SqliteDirectiveContextAdapter(db_file).store_directive_context(
                {
                    "context_id": "ctx-workbench-ui",
                    "portal_instance_id": "fnd",
                    "tool_id": "workbench_ui",
                    "subject_hyphae_hash": row_identity["hyphae_hash"],
                    "subject_version_hash": document_identity["version_hash"],
                    "nimm_state": {"navigation": "focused"},
                    "aitas_state": {"attention": "selected"},
                    "scope": {"surface_id": "system.tools.workbench_ui"},
                    "provenance": {"policy_source": "test_seed"},
                }
            )

            bundle = build_portal_workbench_ui_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=None,
                authority_db_file=db_file,
                surface_query={"document": "system:anthology", "row": "1-1-2", "overlay": "show"},
            )

            overlay_section = next(section for section in bundle["inspector"]["sections"] if section["title"] == "Directive Overlay")
            self.assertEqual(overlay_section["rows"][0]["value"], "loaded")
            catalog = datum_store.read_authoritative_datum_documents({"tenant_id": "fnd"})
            document = next(item for item in catalog.documents if item.document_id == "system:anthology")
            row = next(item for item in document.rows if item.datum_address == "1-1-2")
            self.assertEqual(row.raw[0][2], "CHILD")


if __name__ == "__main__":
    unittest.main()
