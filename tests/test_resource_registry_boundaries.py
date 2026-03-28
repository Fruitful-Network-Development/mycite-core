from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_registry_module():
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module("_shared.portal.data_engine.resource_registry")


class ResourceRegistryBoundaryTests(unittest.TestCase):
    def test_local_index_does_not_discover_root_files(self):
        registry = _load_registry_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            (data_root / "samras-msn.legacy.json").write_text(
                json.dumps({"4-1-9": [["4-1-9", "2-1-1", "9"], ["legacy"]]}, indent=2) + "\n",
                encoding="utf-8",
            )
            payload = registry.load_index(data_root, scope=registry.LOCAL_SCOPE)
            self.assertEqual(payload.get("schema"), "mycite.portal.resources.index.local.v1")
            self.assertEqual(payload.get("resources"), [])

    def test_normalization_reindexes_iterations_from_one(self):
        registry = _load_registry_module()
        payload = {
            "4-1-4": [["4-1-4", "2-1-7", "4"], ["row-four"]],
            "4-1-9": [["4-1-9", "2-1-7", "9"], ["row-nine"]],
            "4-1-12": [["4-1-12", "2-1-7", "12"], ["row-twelve"]],
        }
        normalized = registry.normalize_anthology_compatible_payload(payload)
        self.assertEqual(list(normalized.keys()), ["4-1-1", "4-1-2", "4-1-3"])

    def test_local_index_surfaces_legacy_top_level_resources_in_resources_root(self):
        registry = _load_registry_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            resources_root = data_root / "resources"
            resources_root.mkdir(parents=True, exist_ok=True)
            (resources_root / "rec.3-2-3-17-77-1-6-4-1-4.txa.json").write_text(
                json.dumps({"schema": "legacy.rec", "updated_at": 12345}) + "\n",
                encoding="utf-8",
            )
            payload = registry.load_index(data_root, scope=registry.LOCAL_SCOPE)
            resources = payload.get("resources") if isinstance(payload.get("resources"), list) else []
            self.assertEqual(len(resources), 1)
            self.assertEqual(resources[0].get("resource_name"), "rec.3-2-3-17-77-1-6-4-1-4.txa.json")
            self.assertEqual(resources[0].get("status"), "legacy_root")
            compatibility = payload.get("compatibility") if isinstance(payload.get("compatibility"), dict) else {}
            self.assertEqual(compatibility.get("legacy_root_mode"), "read_only_compat")
            self.assertTrue(bool(compatibility.get("migration_recommended")))

    def test_migrate_legacy_root_rec_files_moves_to_local_layout(self):
        registry = _load_registry_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            root_file = data_root / "resources" / "rec.3-2-3-17-77-1-6-4-1-4.msn.json"
            root_file.parent.mkdir(parents=True, exist_ok=True)
            root_file.write_text(json.dumps({"resource_id": "local:test"}) + "\n", encoding="utf-8")
            report = registry.migrate_legacy_root_rec_files(data_root, apply_changes=True)
            self.assertTrue(report.get("ok"))
            self.assertEqual(report.get("count"), 1)
            self.assertFalse(root_file.exists())
            migrated = data_root / "resources" / "local" / "rec.3-2-3-17-77-1-6-4-1-4.msn.json"
            self.assertTrue(migrated.exists())

    def test_remove_inherited_source_only_removes_target_source(self):
        registry = _load_registry_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            data_root = Path(tmpdir)
            registry.ensure_layout(data_root)
            source_a = "7-7-7"
            source_b = "8-8-8"
            path_a = registry.resource_file_path(
                data_root, scope=registry.INHERITED_SCOPE, source_msn_id=source_a, resource_name="samras.txa"
            )
            path_b = registry.resource_file_path(
                data_root, scope=registry.INHERITED_SCOPE, source_msn_id=source_b, resource_name="samras.txa"
            )
            registry.write_resource_file(path_a, {"schema": "x", "anthology_compatible_payload": {"4-1-1": [["4-1-1"], ["a"]]}})
            registry.write_resource_file(path_b, {"schema": "x", "anthology_compatible_payload": {"4-1-1": [["4-1-1"], ["b"]]}})
            registry.upsert_index_entry(
                data_root,
                scope=registry.INHERITED_SCOPE,
                entry={
                    "resource_id": f"foreign:{source_a}:samras.txa",
                    "resource_name": "samras.txa.json",
                    "resource_kind": "inherited_snapshot",
                    "scope": "inherited",
                    "source_msn_id": source_a,
                    "path": str(path_a),
                    "version_hash": "a",
                    "updated_at": 1,
                    "status": "synced",
                },
            )
            registry.upsert_index_entry(
                data_root,
                scope=registry.INHERITED_SCOPE,
                entry={
                    "resource_id": f"foreign:{source_b}:samras.txa",
                    "resource_name": "samras.txa.json",
                    "resource_kind": "inherited_snapshot",
                    "scope": "inherited",
                    "source_msn_id": source_b,
                    "path": str(path_b),
                    "version_hash": "b",
                    "updated_at": 1,
                    "status": "synced",
                },
            )
            result = registry.remove_inherited_source(data_root, source_msn_id=source_a)
            self.assertEqual(result.get("removed_count"), 1)
            idx = registry.load_index(data_root, scope=registry.INHERITED_SCOPE)
            resources = idx.get("resources") or []
            self.assertEqual(len(resources), 1)
            self.assertEqual((resources[0] or {}).get("source_msn_id"), source_b)


if __name__ == "__main__":
    unittest.main()
