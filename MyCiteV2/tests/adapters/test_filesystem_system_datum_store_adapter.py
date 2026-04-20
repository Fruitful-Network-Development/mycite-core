from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import FilesystemSystemDatumStoreAdapter
from MyCiteV2.packages.ports.datum_store import (
    AuthoritativeDatumDocumentPort,
    AuthoritativeDatumDocumentRequest,
    SystemDatumStorePort,
    SystemDatumStoreRequest,
)


class FilesystemSystemDatumStoreAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemSystemDatumStoreAdapter(Path(temp_dir))
            self.assertIsInstance(adapter, SystemDatumStorePort)
            self.assertIsInstance(adapter, AuthoritativeDatumDocumentPort)

    def test_reads_canonical_system_anthology(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "system").mkdir(parents=True)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps(
                    {
                        "0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]],
                        "0-0-2": [["0-0-2", "~", "0-0-0"], ["time-incramental-unit"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "payloads" / "cache" / "sc.example.txa.json").write_text("{}\n", encoding="utf-8")

            result = FilesystemSystemDatumStoreAdapter(data_dir).read_system_resource_workbench(
                SystemDatumStoreRequest(tenant_id="fnd")
            )

            payload = result.to_dict()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["row_count"], 2)
            self.assertEqual([row["resource_id"] for row in payload["rows"]], ["0-0-1", "0-0-2"])
            self.assertNotIn("legacy", json.dumps(payload["source_files"]))

    def test_missing_canonical_anthology_is_unhealthy(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            data_dir.mkdir(parents=True, exist_ok=True)

            result = FilesystemSystemDatumStoreAdapter(data_dir).read_system_resource_workbench(
                {"tenant_id": "tff"}
            )

            payload = result.to_dict()
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["row_count"], 0)
            self.assertEqual(payload["materialization_status"]["canonical_source"], "missing")
            self.assertEqual(payload["source_files"]["anthology"], str(data_dir / "system" / "anthology.json"))

    def test_reads_authoritative_catalog_with_sandbox_source_and_anchor_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "system" / "sources" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                json.dumps(
                    {
                        "3-1-2": [["3-1-2", "2-0-2", "0"], ["SAMRAS-babelette-msn_id"]],
                        "3-1-3": [["3-1-3", "2-1-1", "0"], ["title-babelette"]],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps(
                    {
                        "anchor_file_version": "<hash here>",
                        "datum_addressing_abstraction_space": {
                            "4-2-118": [
                                ["4-2-118", "rf.3-1-2", "3-2-3-17-77-1", "rf.3-1-3", "HERE"],
                                ["summit_county_cities"],
                            ]
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = FilesystemSystemDatumStoreAdapter(data_dir).read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            )

            payload = result.to_dict()
            sandbox_document = next(
                document
                for document in payload["documents"]
                if document["source_kind"] == "sandbox_source"
            )
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["document_count"], 2)
            self.assertEqual(sandbox_document["tool_id"], "cts_gis")
            self.assertEqual(sandbox_document["anchor_document_name"], "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json")
            self.assertEqual(sandbox_document["anchor_rows"][1]["datum_address"], "3-1-3")
            self.assertEqual(sandbox_document["rows"][0]["raw"][0][4], "HERE")
            self.assertEqual(payload["readiness_status"]["derived_materialization"], "partial")
            self.assertIn(
                "No derived payload cache JSON files were found under data/payloads/cache.",
                payload["warnings"],
            )

    def test_anchor_precedence_prefers_canonical_anchor_when_other_tool_json_is_present(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                json.dumps({"3-1-3": [["3-1-3", "2-1-1", "0"], ["canonical-anchor"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "tool.fallback.json").write_text(
                json.dumps({"3-1-3": [["3-1-3", "2-1-1", "0"], ["ignored-anchor"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"4-2-1": [["4-2-1", "rf.3-1-3", "HERE"], ["row"]]}) + "\n",
                encoding="utf-8",
            )

            payload = FilesystemSystemDatumStoreAdapter(data_dir).read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            ).to_dict()
            sandbox_document = next(
                document
                for document in payload["documents"]
                if document["source_kind"] == "sandbox_source"
            )
            self.assertEqual(
                sandbox_document["anchor_document_name"],
                "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json",
            )

    def test_invalid_anchor_json_surfaces_warning_without_silent_projection_recovery(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                '{"3-1-3": [["3-1-3", "2-1-1", "0"], ["broken-anchor"]],}\n',
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"4-2-1": [["4-2-1", "rf.3-1-3", "HERE"], ["row"]]}) + "\n",
                encoding="utf-8",
            )

            payload = FilesystemSystemDatumStoreAdapter(data_dir).read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            ).to_dict()
            sandbox_document = next(
                document
                for document in payload["documents"]
                if document["source_kind"] == "sandbox_source"
            )
            self.assertEqual(sandbox_document["anchor_rows"], [])
            self.assertIn(
                "Supporting sandbox anchor document is not valid JSON",
                " ".join(sandbox_document["warnings"]),
            )

    def test_cts_gis_catalog_includes_precinct_subdirectory_sources(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            (data_dir / "system" / "sources").mkdir(parents=True)
            (data_dir / "payloads" / "cache").mkdir(parents=True)
            (data_dir / "sandbox" / "cts-gis" / "sources" / "precincts").mkdir(parents=True)
            (data_dir / "system" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                json.dumps({"3-1-3": [["3-1-3", "2-1-1", "0"], ["title-babelette"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "sc.root.json").write_text(
                json.dumps({"4-2-1": [["4-2-1", "rf.3-1-3", "ROOT"], ["row"]]}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "sandbox" / "cts-gis" / "sources" / "precincts" / "sc.precinct.json").write_text(
                json.dumps({"4-2-1": [["4-2-1", "rf.3-1-3", "PRECINCT"], ["row"]]}) + "\n",
                encoding="utf-8",
            )

            payload = FilesystemSystemDatumStoreAdapter(data_dir).read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            ).to_dict()
            sandbox_docs = [
                document
                for document in payload["documents"]
                if document["source_kind"] == "sandbox_source"
            ]
            self.assertEqual(len(sandbox_docs), 2)
            relative_paths = {document["relative_path"] for document in sandbox_docs}
            self.assertIn("sandbox/cts-gis/sources/sc.root.json", relative_paths)
            self.assertIn("sandbox/cts-gis/sources/precincts/sc.precinct.json", relative_paths)

    def test_capability_paths_allow_remapped_layout_without_behavior_change(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "default_data"
            remap = root / "packaged_layout"
            (data_dir / "public").mkdir(parents=True)
            (remap / "system_root").mkdir(parents=True)
            (remap / "system_sources_root").mkdir(parents=True)
            (remap / "payload_cache_root").mkdir(parents=True)
            (remap / "sandbox_root" / "cts-gis" / "sources").mkdir(parents=True)
            (remap / "system_root" / "anthology.json").write_text(
                json.dumps({"0-0-1": [["0-0-1", "~", "0-0-0"], ["time-ordinal-position"]]}) + "\n",
                encoding="utf-8",
            )
            (remap / "system_sources_root" / "sc.example.json").write_text("{}\n", encoding="utf-8")
            (remap / "sandbox_root" / "cts-gis" / "tool.3-2-3-17-77-1-6-4-1-4.cts-gis.json").write_text(
                json.dumps({"3-1-3": [["3-1-3", "2-1-1", "0"], ["title-babelette"]]}) + "\n",
                encoding="utf-8",
            )
            (remap / "sandbox_root" / "cts-gis" / "sources" / "sc.example.json").write_text(
                json.dumps({"4-2-1": [["4-2-1", "rf.3-1-3", "HERE"], ["row"]]}) + "\n",
                encoding="utf-8",
            )
            adapter = FilesystemSystemDatumStoreAdapter(data_dir).with_path_capabilities(
                system_anthology_file=remap / "system_root" / "anthology.json",
                system_sources_dir=remap / "system_sources_root",
                payload_cache_dir=remap / "payload_cache_root",
                sandbox_root_dir=remap / "sandbox_root",
            )

            payload = adapter.read_authoritative_datum_documents(
                AuthoritativeDatumDocumentRequest(tenant_id="fnd")
            ).to_dict()
            sandbox_docs = [
                document
                for document in payload["documents"]
                if document["source_kind"] == "sandbox_source"
            ]
            self.assertEqual(payload["document_count"], 2)
            self.assertEqual(payload["readiness_status"]["anthology_status"], "loaded")
            self.assertEqual(payload["readiness_status"]["system_source_count"], 1)
            self.assertEqual(payload["readiness_status"]["payload_cache_count"], 0)
            self.assertEqual(payload["readiness_status"]["sandbox_source_document_count"], 1)
            self.assertEqual(len(sandbox_docs), 1)
            self.assertTrue(str(remap / "sandbox_root" / "cts-gis" / "sources" / "sc.example.json") in {
                doc["relative_path"] for doc in sandbox_docs
            })


if __name__ == "__main__":
    unittest.main()
