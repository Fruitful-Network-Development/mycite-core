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
from MyCiteV2.packages.ports.datum_store import SystemDatumStorePort, SystemDatumStoreRequest


class FilesystemSystemDatumStoreAdapterTests(unittest.TestCase):
    def test_adapter_conforms_to_port(self) -> None:
        with TemporaryDirectory() as temp_dir:
            adapter = FilesystemSystemDatumStoreAdapter(Path(temp_dir))
            self.assertIsInstance(adapter, SystemDatumStorePort)

    def test_reads_canonical_system_anthology_and_ignores_legacy_root_file(self) -> None:
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
            (data_dir / "anthology.json").write_text(json.dumps({"legacy-only": []}) + "\n", encoding="utf-8")

            result = FilesystemSystemDatumStoreAdapter(data_dir).read_system_resource_workbench(
                SystemDatumStoreRequest(tenant_id="fnd")
            )

            payload = result.to_dict()
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["row_count"], 2)
            self.assertEqual([row["resource_id"] for row in payload["rows"]], ["0-0-1", "0-0-2"])
            self.assertNotIn("legacy-only", json.dumps(payload["rows"]))
            self.assertEqual(payload["materialization_status"]["legacy_root_fallback"], "blocked")
            self.assertEqual(payload["materialization_status"]["legacy_root_conflict_count"], 1)
            self.assertIn("Legacy root datum files exist", " ".join(payload["warnings"]))

    def test_missing_canonical_anthology_is_unhealthy_without_root_fallback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "anthology.json").write_text(json.dumps({"legacy-only": []}) + "\n", encoding="utf-8")

            result = FilesystemSystemDatumStoreAdapter(data_dir).read_system_resource_workbench(
                {"tenant_id": "tff"}
            )

            payload = result.to_dict()
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["row_count"], 0)
            self.assertEqual(payload["materialization_status"]["canonical_source"], "missing")
            self.assertEqual(payload["source_files"]["ignored_legacy_root_files"], [str(data_dir / "anthology.json")])


if __name__ == "__main__":
    unittest.main()
