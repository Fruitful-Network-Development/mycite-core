from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_system_workspace_runtime import build_system_workspace_bundle
from MyCiteV2.packages.adapters.sql import SqliteDirectiveContextAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.state_machine.portal_shell import (
    PortalScope,
    SYSTEM_ROOT_SURFACE_ID,
    TRANSITION_FOCUS_DATUM,
    initial_portal_shell_state,
    reduce_portal_shell_state,
)


class PortalSystemWorkspaceDirectiveContextTests(unittest.TestCase):
    def test_system_workspace_reads_selected_datum_directive_overlay_without_mutating_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True, exist_ok=True)
            public_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "1-0-1": [["1-0-1", "~", "ROOT"], ["anchor-root"]],
                        "1-1-1": [["1-1-1", "~", "1-0-1"], ["first-datum"]],
                        "1-1-2": [["1-1-2", "~", "1-1-1"], ["second-datum"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            scope = PortalScope(scope_id="fnd", capabilities=("fnd_peripheral_routing",))
            base_state = initial_portal_shell_state(surface_id=SYSTEM_ROOT_SURFACE_ID, portal_scope=scope.to_dict())
            datum_state = reduce_portal_shell_state(
                active_surface_id=SYSTEM_ROOT_SURFACE_ID,
                portal_scope=scope.to_dict(),
                current_state=base_state,
                transition={"kind": TRANSITION_FOCUS_DATUM, "file_key": "anthology", "datum_id": "1-1-2"},
                seed_anchor_file=False,
            )

            build_system_workspace_bundle(
                portal_scope=scope,
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=datum_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )

            datum_store = SqliteSystemDatumStoreAdapter(db_file)
            document_identity = datum_store.read_document_version_identity(
                tenant_id="fnd",
                document_id="system:anthology",
            )
            datum_identity = datum_store.read_datum_semantic_identity(
                tenant_id="fnd",
                document_id="system:anthology",
                datum_address="1-1-2",
            )
            SqliteDirectiveContextAdapter(db_file).store_directive_context(
                {
                    "context_id": "ctx-selected-datum",
                    "portal_instance_id": "fnd",
                    "tool_id": "system_workspace",
                    "subject_hyphae_hash": datum_identity["hyphae_hash"],
                    "subject_version_hash": document_identity["version_hash"],
                    "nimm_state": {"navigation": "focused", "mediation": "row"},
                    "aitas_state": {"attention": "selected", "space": "system"},
                    "scope": {"surface_id": "system.root", "datum_id": "1-1-2"},
                    "provenance": {"policy_source": "test_seed"},
                }
            )

            bundle = build_system_workspace_bundle(
                portal_scope=scope,
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=datum_state,
                data_dir=data_dir,
                public_dir=public_dir,
                audit_storage_file=None,
                tool_rows=[],
                authority_db_file=db_file,
                authority_mode="sql_primary",
            )

            document = bundle["surface_payload"]["workspace"]["document"]
            self.assertEqual(document["selected_datum"]["datum_id"], "1-1-2")
            self.assertEqual(document["selected_datum"]["raw"][0][0], "1-1-2")
            directive_context = document["directive_context"]
            self.assertEqual(directive_context["subject_level"], "datum")
            self.assertEqual(directive_context["overlay"]["context_id"], "ctx-selected-datum")
            self.assertEqual(directive_context["overlay"]["nimm_state"]["navigation"], "focused")
            directive_section = next(
                section for section in bundle["inspector"]["sections"] if section["title"] == "Directive context"
            )
            self.assertEqual(directive_section["rows"][0]["value"], "datum")


if __name__ == "__main__":
    unittest.main()
