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
from MyCiteV2.instances._shared.runtime.portal_cts_gis_runtime import run_portal_cts_gis_action
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.packages.adapters.sql import SqliteDirectiveContextAdapter, SqliteSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocument,
    AuthoritativeDatumDocumentCatalogResult,
    AuthoritativeDatumDocumentRow,
)
from MyCiteV2.packages.state_machine.portal_shell import PortalScope


class WorkbenchUiRuntimeTests(unittest.TestCase):
    def _cts_gis_authoritative_document(self) -> AuthoritativeDatumDocument:
        def ascii_bits(value: str, width: int = 256) -> str:
            bitstream = "".join(format(ord(char), "08b") for char in value)
            return bitstream.ljust(width, "0")

        def row(datum_address: str, node_address: str, title: str) -> AuthoritativeDatumDocumentRow:
            return AuthoritativeDatumDocumentRow(
                datum_address=datum_address,
                raw=[
                    [datum_address, "rf.3-1-2", node_address, "rf.3-1-3", ascii_bits(title)],
                    [title.replace(" ", "_")],
                ],
            )

        return AuthoritativeDatumDocument(
            document_id="sandbox:cts_gis:sc.example.json",
            source_kind="sandbox_source",
            document_name="sc.example.json",
            relative_path="sandbox/cts-gis/sources/sc.example.json",
            tool_id="cts_gis",
            rows=(
                row("4-2-1", "3-2-3-17-77-1", "ALPHA STREET"),
                row("4-2-2", "3-2-3-17-77-2", "BETA STREET"),
                row("4-2-3", "3-2-3-17-77-2", "GAMMA STREET"),
            ),
        )

    def test_workbench_ui_defaults_to_cts_gis_document_when_available(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["root"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps(
                    {
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]],
                        "1-1-2": [["1-1-2", "1-1-1", "PROFILE"], ["profile"]],
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
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                authority_db_file=db_file,
            )

            workspace = envelope["surface_payload"]["workspace"]
            selected_document_id = workspace["selected_document"]["document_id"]

            self.assertTrue(selected_document_id.startswith("sandbox:cts_gis:"))
            self.assertEqual(envelope["canonical_query"]["document"], selected_document_id)
            self.assertEqual(workspace["query"]["document"], selected_document_id)
            composition = envelope["shell_composition"]
            self.assertFalse(composition["workbench_collapsed"])
            self.assertFalse(composition["interface_panel_collapsed"])
            self.assertTrue(composition["regions"]["workbench"]["visible"])
            self.assertTrue(composition["regions"]["interface_panel"]["visible"])

    def test_shell_route_keeps_workbench_ui_runtime_owned_and_sql_context_led(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
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

            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.workbench_ui",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                private_dir=None,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
                authority_db_file=db_file,
            )

            self.assertFalse(envelope["reducer_owned"])
            self.assertEqual(envelope["surface_id"], "system.tools.workbench_ui")
            self.assertEqual(envelope["shell_state"], {"schema": "mycite.v2.portal.shell.state.v1"})
            self.assertIsNone(envelope["shell_composition"]["shell_state"])
            self.assertEqual(envelope["surface_payload"]["kind"], "workbench_ui_surface")
            self.assertIn("document", envelope["canonical_query"])
            for key in ("file", "datum", "object", "verb"):
                self.assertNotIn(key, envelope["canonical_query"])

            control_panel = envelope["shell_composition"]["regions"]["control_panel"]
            self.assertEqual(
                [item["label"] for item in control_panel["context_items"][:5]],
                ["Document", "Version", "Selected Row", "Row Identity", "Document Sort"],
            )
            self.assertEqual(control_panel["surface_label"], "WORKBENCH UI")

            workspace = envelope["surface_payload"]["workspace"]
            self.assertEqual(workspace["query"]["document"], envelope["canonical_query"]["document"])
            self.assertEqual(workspace["query"]["row"], envelope["canonical_query"]["row"])

    def test_shell_route_forwards_explicit_surface_query_to_workbench_ui_runtime(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
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
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]]}) + "\n",
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.workbench_ui",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                    "surface_query": {
                        "document": "system:anthology",
                        "sort": "hyphae_hash",
                        "dir": "asc",
                        "source": "hide",
                        "overlay": "hide",
                        "row": "1-1-2",
                    },
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                private_dir=None,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
                authority_db_file=db_file,
            )

            self.assertEqual(
                envelope["canonical_query"],
                {
                    "document": "system:anthology",
                    "document_sort": "version_hash",
                    "document_dir": "asc",
                    "sort": "hyphae_hash",
                    "dir": "asc",
                    "group": "flat",
                    "workbench_lens": "interpreted",
                    "source": "hide",
                    "overlay": "hide",
                    "row": "1-1-2",
                },
            )
            workspace = envelope["surface_payload"]["workspace"]
            self.assertEqual(workspace["query"]["document"], "system:anthology")
            self.assertEqual(workspace["query"]["sort"], "hyphae_hash")
            self.assertEqual(workspace["query"]["dir"], "asc")
            self.assertEqual(workspace["query"]["source"], "hide")
            self.assertEqual(workspace["query"]["overlay"], "hide")
            self.assertEqual(workspace["query"]["row"], "1-1-2")
            self.assertEqual(workspace["selected_document"]["document_id"], "system:anthology")
            self.assertEqual(workspace["selected_row"]["datum_address"], "1-1-2")

    def test_direct_workbench_ui_endpoint_matches_shell_runtime_envelope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
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
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]]}) + "\n",
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            direct_envelope = run_portal_workbench_ui(
                {
                    "schema": "mycite.v2.portal.system.tools.workbench_ui.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                    "surface_query": {
                        "document": "system:anthology",
                        "sort": "hyphae_hash",
                        "dir": "asc",
                        "source": "hide",
                        "overlay": "hide",
                        "row": "1-1-2",
                    },
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                authority_db_file=db_file,
            )
            shell_envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.workbench_ui",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                    "surface_query": {
                        "document": "system:anthology",
                        "sort": "hyphae_hash",
                        "dir": "asc",
                        "source": "hide",
                        "overlay": "hide",
                        "row": "1-1-2",
                    },
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                data_dir=data_dir,
                public_dir=public_dir,
                private_dir=None,
                audit_storage_file=None,
                webapps_root=None,
                tool_exposure_policy=None,
                authority_db_file=db_file,
            )

            self.assertEqual(direct_envelope["surface_id"], shell_envelope["surface_id"])
            self.assertEqual(direct_envelope["reducer_owned"], shell_envelope["reducer_owned"])
            self.assertEqual(direct_envelope["canonical_query"], shell_envelope["canonical_query"])
            self.assertEqual(direct_envelope["canonical_url"], shell_envelope["canonical_url"])
            self.assertEqual(direct_envelope["shell_composition"], shell_envelope["shell_composition"])
            self.assertEqual(
                direct_envelope["surface_payload"]["workspace"]["query"],
                shell_envelope["surface_payload"]["workspace"]["query"],
            )

    def test_workbench_ui_runtime_projects_document_table_and_row_grid(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
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
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]]}) + "\n",
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
            document_table = next(
                section for section in envelope["surface_payload"]["sections"] if section["title"] == "Document Table"
            )
            row_table = next(section for section in envelope["surface_payload"]["sections"] if section["title"] == "Datum Grid")
            self.assertEqual(len(document_table["items"]), 2)
            self.assertIn("version_hash", document_table["items"][0])
            self.assertEqual(row_table["title"], "Datum Grid")
            self.assertEqual(len(row_table["items"]), 2)
            self.assertTrue(row_table["items"][0]["hyphae_hash"])

    def test_workbench_ui_falls_back_to_first_document_when_no_cts_gis_document_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
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

            bundle = build_portal_workbench_ui_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=None,
                authority_db_file=db_file,
                surface_query={},
            )

            workspace = bundle["surface_payload"]["workspace"]
            self.assertEqual(workspace["selected_document"]["document_id"], "system:anthology")
            self.assertEqual(workspace["query"]["document"], "system:anthology")

    def test_workbench_ui_document_table_supports_version_hash_filter_and_sort(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
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
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps(
                    {
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]],
                        "1-1-2": [["1-1-2", "1-1-1", "PROFILE"], ["profile"]],
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
            anthology_hash = datum_store.read_document_version_identity(
                tenant_id="fnd",
                document_id="system:anthology",
            )["version_hash"]

            bundle = build_portal_workbench_ui_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=None,
                authority_db_file=db_file,
                surface_query={
                    "document_filter": anthology_hash[:12],
                    "document_sort": "version_hash",
                    "document_dir": "desc",
                },
            )

            document_table = next(
                section for section in bundle["surface_payload"]["sections"] if section["title"] == "Document Table"
            )
            query_controls = next(
                section for section in bundle["surface_payload"]["sections"] if section["title"] == "Query Controls"
            )
            self.assertEqual(len(document_table["items"]), 1)
            self.assertEqual(document_table["items"][0]["document_id"], "system:anthology")
            self.assertEqual(document_table["items"][0]["version_hash"], anthology_hash)
            controls = {row["label"]: row["value"] for row in query_controls["rows"]}
            self.assertEqual(controls["document filter"], anthology_hash[:12].lower())
            self.assertEqual(controls["document sort"], "version_hash")
            self.assertEqual(controls["document direction"], "desc")

    def test_workbench_ui_row_filter_supports_hyphae_hash(self) -> None:
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
            row_identity = datum_store.read_datum_semantic_identity(
                tenant_id="fnd",
                document_id="system:anthology",
                datum_address="1-1-2",
            )

            bundle = build_portal_workbench_ui_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=None,
                authority_db_file=db_file,
                surface_query={
                    "document": "system:anthology",
                    "filter": row_identity["hyphae_hash"][:12],
                    "sort": "hyphae_hash",
                    "dir": "asc",
                },
            )

            row_table = next(section for section in bundle["surface_payload"]["sections"] if section["title"] == "Datum Grid")
            self.assertEqual(len(row_table["items"]), 1)
            self.assertEqual(row_table["items"][0]["datum_address"], "1-1-2")

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

    def test_workbench_ui_supports_grouping_lens_visibility_and_selection_markers(self) -> None:
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
                        "2-1-1": [["2-1-1", "1-1-1", "CHILD"], ["child-a"]],
                        "2-2-1": [["2-2-1", "1-1-1", "CHILD"], ["child-b"]],
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

            bundle = build_portal_workbench_ui_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=None,
                authority_db_file=db_file,
                surface_query={
                    "document": "system:anthology",
                    "group": "layer_value_group",
                    "workbench_lens": "raw",
                    "source": "hide",
                    "row": "2-2-1",
                },
            )

            workspace = bundle["surface_payload"]["workspace"]
            document_table = workspace["document_table"]
            datum_grid = workspace["datum_grid"]
            inspector_titles = [section["title"] for section in bundle["inspector"]["sections"]]

            self.assertEqual(workspace["query"]["group"], "layer_value_group")
            self.assertEqual(workspace["query"]["workbench_lens"], "raw")
            self.assertEqual(workspace["query"]["source"], "hide")
            self.assertTrue(document_table["sticky_header"])
            self.assertTrue(datum_grid["sticky_header"])
            self.assertEqual(
                [group["title"] for group in datum_grid["groups"]],
                ["Layer 1 / Value Group 1", "Layer 2 / Value Group 1", "Layer 2 / Value Group 2"],
            )
            grouped_rows = [row for group in datum_grid["groups"] for row in group["items"]]
            selected = next(row for row in grouped_rows if row["selected"])
            self.assertEqual(selected["datum_address"], "2-2-1")
            self.assertLessEqual(len(workspace["selected_document"]["version_hash_short"]), 12)
            self.assertLessEqual(len(workspace["selected_row"]["hyphae_hash_short"]), 12)
            self.assertIn("raw_preview", [column["key"] for column in datum_grid["columns"]])
            self.assertNotIn("labels", [column["key"] for column in datum_grid["columns"]])
            self.assertNotIn("Source Metadata", inspector_titles)

    def test_workbench_ui_runtime_projects_navigation_requests_for_documents_and_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
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
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"1-1-1": [["1-1-1", "~", "ROOT"], ["sandbox"]]}) + "\n",
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            bundle = build_portal_workbench_ui_surface_bundle(
                portal_scope=PortalScope(scope_id="fnd", capabilities=("datum_recognition",)),
                portal_domain="fruitfulnetworkdevelopment.com",
                shell_state=None,
                authority_db_file=db_file,
                surface_query={
                    "document": "system:anthology",
                    "document_sort": "document_id",
                    "document_dir": "asc",
                    "row": "1-1-1",
                    "group": "flat",
                },
            )

            workspace = bundle["surface_payload"]["workspace"]
            other_document_id = next(
                document["document_id"]
                for document in workspace["document_table"]["rows"]
                if document["document_id"] != "system:anthology"
            )
            next_document = workspace["navigation"]["next_document"] or workspace["navigation"]["previous_document"]
            next_row = workspace["navigation"]["next_row"]

            self.assertEqual(next_document["id"], other_document_id)
            self.assertEqual(next_document["shell_request"]["surface_query"]["document"], other_document_id)
            self.assertNotIn("row", next_document["shell_request"]["surface_query"])
            self.assertEqual(next_row["shell_request"]["surface_query"]["row"], "1-1-2")
            self.assertEqual(next_row["shell_request"]["surface_query"]["document"], "system:anthology")
            self.assertTrue(all(document.get("href") and document.get("shell_request") for document in workspace["document_table"]["rows"]))
            self.assertTrue(all(row.get("href") and row.get("shell_request") for row in workspace["datum_grid"]["rows"]))

    def test_post_apply_rows_are_visible_in_workbench_ui(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            public_dir = root / "public"
            db_file = root / "authority.sqlite3"
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            public_dir.mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "1-1-1": [["1-1-1", "~", "ROOT"], ["root"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            source_rows = {
                row.datum_address: row.raw
                for row in self._cts_gis_authoritative_document().rows
            }
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"datum_addressing_abstraction_space": source_rows}) + "\n",
                encoding="utf-8",
            )
            SqliteSystemDatumStoreAdapter(db_file).bootstrap_from_filesystem(
                data_dir=data_dir,
                public_dir=public_dir,
                tenant_id="fnd",
            )

            staged = run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": {
                        "selected_node_id": "3-2-3-17-77-1",
                        "source": {"attention_document_id": "sandbox:cts_gis:sc.example.json"},
                    },
                    "action_kind": "stage_insert_yaml",
                    "action_payload": {
                        "stage_document": {
                            "schema": "mycite.v2.cts_gis.stage_insert.v1",
                            "document_id": "sandbox:cts_gis:sc.example.json",
                            "document_name": "sc.example.json",
                            "operation": "insert_datums",
                            "datums": [
                                {
                                    "family": "administrative_street",
                                    "valueGroup": 2,
                                    "targetNodeAddress": "3-2-3-17-77-1",
                                    "title": "MAIN STREET",
                                    "references": [
                                        {"type": "title", "text": "MAIN STREET"},
                                        {"type": "msn-samras", "nodeAddress": "3-2-3-17-77-1"},
                                    ],
                                }
                            ],
                        }
                    },
                },
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            preview = run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": staged["surface_payload"]["tool_state"],
                    "action_kind": "preview_apply",
                    "action_payload": {},
                },
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            run_portal_cts_gis_action(
                {
                    "schema": "mycite.v2.portal.system.tools.cts_gis.action.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition", "spatial_projection"]},
                    "tool_state": preview["surface_payload"]["tool_state"],
                    "action_kind": "apply_stage",
                    "action_payload": {},
                },
                data_dir=None,
                authority_db_file=db_file,
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )

            envelope = run_portal_workbench_ui(
                {
                    "schema": "mycite.v2.portal.system.tools.workbench_ui.request.v1",
                    "portal_scope": {"scope_id": "fnd", "capabilities": ["datum_recognition"]},
                    "surface_query": {"document": "sandbox:cts_gis:sc.example.json", "row": "4-2-2"},
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                authority_db_file=db_file,
            )

            self.assertEqual(envelope["surface_payload"]["workspace"]["selected_row"]["datum_address"], "4-2-2")
            self.assertEqual(envelope["surface_payload"]["workspace"]["selected_row"]["labels"], "MAIN_STREET")


if __name__ == "__main__":
    unittest.main()
