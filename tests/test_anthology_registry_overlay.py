from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module(name: str):
    portals_root = Path(__file__).resolve().parents[1] / "portals"
    token = str(portals_root)
    if token not in sys.path:
        sys.path.insert(0, token)
    return importlib.import_module(name)


def _load_fnd_storage_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "portals"
        / "_shared"
        / "runtime"
        / "flavors"
        / "fnd"
        / "data"
        / "storage_json.py"
    )
    spec = importlib.util.spec_from_file_location("fnd_storage_json_test_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnthologyRegistryOverlayTests(unittest.TestCase):
    def test_normalized_schema_detects_definition_tuple_selection(self):
        schema = _load_module("_shared.portal.data_engine.anthology_schema")
        definition_row = {
            "identifier": "1-1-2",
            "label": "nominal-bacillete-16",
            "pairs": [{"reference": "0-0-6", "magnitude": "16"}],
        }
        datum, warnings = schema.normalize_row(definition_row, source_scope="base", strict=True)
        self.assertIsNotNone(datum)
        self.assertFalse(warnings)
        self.assertEqual(datum.row_kind, "definition")

        tuple_row = {
            "identifier": "8-2-1",
            "label": "tuple-example",
            "pairs": [
                {"reference": "7-1-1", "magnitude": "a"},
                {"reference": "7-1-2", "magnitude": "b"},
            ],
        }
        tuple_datum, tuple_warnings = schema.normalize_row(tuple_row, source_scope="portal", strict=True)
        self.assertIsNotNone(tuple_datum)
        self.assertFalse(tuple_warnings)
        self.assertEqual(tuple_datum.row_kind, "tuple")

        selection_row = {
            "identifier": "5-0-1",
            "label": "selection-root",
            "pairs": [{"reference": "4-1-1", "magnitude": "0"}],
        }
        selection_datum, selection_warnings = schema.normalize_row(selection_row, source_scope="portal", strict=True)
        self.assertIsNotNone(selection_datum)
        self.assertFalse(selection_warnings)
        self.assertEqual(selection_datum.row_kind, "selection")

    def test_base_registry_and_overlay_merge(self):
        registry_mod = _load_module("_shared.portal.data_engine.anthology_registry")
        overlay_mod = _load_module("_shared.portal.data_engine.anthology_overlay")

        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "anthology-base.json"
            base_payload = {
                "0-0-6": [["0-0-6", "0-0-0", "0"], ["nominal-incramental-unit"]],
                "1-1-2": [["1-1-2", "0-0-6", "16"], ["nominal-bacillete-16"]],
                "5-0-1": [["5-0-1", "1-1-2", "[\"1-1-2\"]"], ["base-root"]],
            }
            base_path.write_text(json.dumps(base_payload, indent=2) + "\n", encoding="utf-8")
            base_registry = registry_mod.load_base_registry(base_path=base_path, strict=True)
            self.assertIn("1-1-2", base_registry.reserved_ids)

            overlay_payload = {
                "5-0-1": [["5-0-1", "1-1-2", "sandbox://samras/txa-samras"], ["portal-root"]],
                "8-1-1": [["8-1-1", "1-1-2", "alpha"], ["portal-specific"]],
            }
            merged = overlay_mod.merge_base_and_overlay(
                base_registry=base_registry,
                overlay_payload=overlay_payload,
                strict=False,
                allow_overlay_override=True,
            )
            self.assertTrue(merged.ok)
            self.assertEqual(merged.source_scope_by_id.get("8-1-1"), "portal")
            self.assertEqual(merged.source_scope_by_id.get("1-1-2"), "base")
            self.assertEqual(merged.source_scope_by_id.get("5-0-1"), "portal")

    def test_overlay_migration_dry_run_and_apply(self):
        registry_mod = _load_module("_shared.portal.data_engine.anthology_registry")
        overlay_mod = _load_module("_shared.portal.data_engine.anthology_overlay")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_path = root / "anthology-base.json"
            base_payload = {
                "0-0-1": [["0-0-1", "0-0-0", "0"], ["top"]],
                "1-1-1": [["1-1-1", "0-0-1", "1"], ["seed"]],
            }
            base_path.write_text(json.dumps(base_payload, indent=2) + "\n", encoding="utf-8")
            overlay_path = root / "anthology.json"
            overlay_payload = {
                "0-0-1": [["0-0-1", "0-0-0", "0"], ["top"]],
                "8-1-1": [["8-1-1", "1-1-1", "x"], ["portal"]],
            }
            overlay_path.write_text(json.dumps(overlay_payload, indent=2) + "\n", encoding="utf-8")

            registry = registry_mod.load_base_registry(base_path=base_path, strict=True)
            dry = overlay_mod.migrate_overlay_file(
                overlay_path=overlay_path,
                base_registry=registry,
                apply_changes=False,
            )
            self.assertIn("0-0-1", dry.removed_duplicate_ids)
            self.assertIn("8-1-1", dry.kept_ids)
            self.assertIn("0-0-1", json.loads(overlay_path.read_text(encoding="utf-8")))

            applied = overlay_mod.migrate_overlay_file(
                overlay_path=overlay_path,
                base_registry=registry,
                apply_changes=True,
            )
            self.assertIn("0-0-1", applied.removed_duplicate_ids)
            updated = json.loads(overlay_path.read_text(encoding="utf-8"))
            self.assertNotIn("0-0-1", updated)
            self.assertIn("8-1-1", updated)

    def test_backward_compat_with_existing_raw_compact_anthology_files(self):
        overlay_mod = _load_module("_shared.portal.data_engine.anthology_overlay")
        repo_root = Path(__file__).resolve().parents[1]
        example_overlay = repo_root / "compose" / "portals" / "state" / "example_portal" / "data" / "anthology.json"
        report = overlay_mod.load_overlay_merge_for_path(
            overlay_path=example_overlay,
            strict=False,
            allow_overlay_override=True,
        )
        self.assertTrue(report.ok)
        self.assertTrue(report.merged_payload)
        self.assertIn("0-0-1", report.merged_payload)

    def test_storage_backend_loads_base_plus_overlay_and_persists_overlay(self):
        storage_mod = _load_fnd_storage_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "anthology.json").write_text(
                json.dumps(
                    {
                        "0-0-1": [["0-0-1", "0-0-0", "0"], ["time-root"]],
                        "8-1-1": [["8-1-1", "1-1-2", "portal"], ["portal-only"]],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            storage = storage_mod.JsonStorageBackend(root)
            rows = storage.load_rows("anthology")
            identifiers = {str(row.get("identifier") or "") for row in rows}
            # Base row loaded from anthology-base.json.
            self.assertIn("1-1-2", identifiers)
            # Portal-local overlay row remains present.
            self.assertIn("8-1-1", identifiers)

            # Persisting should keep overlay semantics and avoid re-writing identical base duplicates.
            persist = storage.persist_rows("anthology", rows)
            self.assertTrue(persist.get("ok"))
            overlay_after = json.loads((root / "anthology.json").read_text(encoding="utf-8"))
            self.assertIn("8-1-1", overlay_after)
            # This row exists in anthology-base.json and should be stripped from overlay output.
            self.assertNotIn("1-1-2", overlay_after)

    def test_canonical_anthology_context_builds_rows_and_compact_payload(self):
        context_mod = _load_module("_shared.portal.data_engine.anthology_context")
        payload = {
            "rows": {
                "8-5-1": {"identifier": "8-5-1", "label": "product", "pairs": [{"reference": "3-1-5", "magnitude": "x"}]},
                "8-4-1": {"identifier": "8-4-1", "label": "supply", "pairs": [{"reference": "3-1-5", "magnitude": "y"}]},
            }
        }
        context = context_mod.build_canonical_anthology_context(overlay_payload=payload)
        self.assertTrue(context.ok)
        self.assertIn("8-5-1", context.rows_by_id)
        self.assertIn("8-4-1", context.rows_by_id)
        self.assertIn("8-5-1", context.compact_payload)


if __name__ == "__main__":
    unittest.main()
