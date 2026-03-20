"""Tests for sandbox resource workbench view-models and staging snapshot."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _shared.portal.sandbox.engine import SandboxEngine
from _shared.portal.sandbox.resource_workbench import (
    build_resource_workbench_view_model,
    build_system_resource_workbench_view_model,
)


class ResourceWorkbenchVmTests(unittest.TestCase):
    def test_workbench_surfaces_anthology_rows_and_samras_rows(self):
        resource = {
            "resource_id": "msn.demo",
            "resource_kind": "msn",
            "kind": "samras_resource",
            "rows_by_address": {"1": ["Root"], "1-1": ["Leaf"]},
            "anthology_compatible_payload": {
                "rows": {
                    "4-0-1": {
                        "row_id": "4-0-1",
                        "identifier": "4-0-1",
                        "label": "L",
                        "layer": 4,
                        "value_group": 0,
                        "reference": "2-1-1",
                        "magnitude": "1",
                    }
                }
            },
        }
        rule_pol = {"4-0-1": {"rule_family": "test_family", "lens_id": "default"}}
        vm = build_resource_workbench_view_model(
            resource_body=resource,
            staged_present=True,
            staged_payload={"note": "staged"},
            datum_understanding={"ok": True, "warnings": ["w1"], "errors": [], "understandings": [{}]},
            rule_policy_by_id=rule_pol,
        )
        self.assertEqual(vm.get("schema"), "mycite.portal.resource.workbench.v1")
        self.assertTrue(vm.get("staged_present"))
        self.assertTrue(vm.get("is_samras_backed"))
        self.assertEqual(len(vm.get("samras_row_summaries") or []), 2)
        self.assertEqual(len(vm.get("anthology_row_summaries") or []), 1)
        layers = vm.get("anthology_layers") or []
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0].get("row_count"), 1)

    def test_peek_stage_payload(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "sandbox" / "resources").mkdir(parents=True)
        (root / "sandbox" / "staging").mkdir(parents=True)
        eng = SandboxEngine(data_root=root)
        eng.save_resource("r1", {"resource_id": "r1", "kind": "x"})
        has_staged, snap = eng.peek_stage_payload("r1")
        self.assertFalse(has_staged)
        self.assertEqual(snap, {})
        stage_path = root / "sandbox" / "staging" / "r1.stage.json"
        stage_path.write_text('{"resource_id": "r1", "staged": true}\n', encoding="utf-8")
        ok, snap2 = eng.peek_stage_payload("r1")
        self.assertTrue(ok)
        self.assertTrue(snap2.get("staged"))
        tmp.cleanup()

    def test_system_resource_workbench_materializes_canonical_files(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "anthology.json").write_text(
            '{"rows":{"1-0-1":{"row_id":"1-0-1","identifier":"1-0-1","label":"A","reference":"2-0-1","magnitude":"1","layer":1,"value_group":0}}}\n',
            encoding="utf-8",
        )
        (root / "samras-txa.legacy.json").write_text(
            '{"rows":{"2-0-1":{"row_id":"2-0-1","identifier":"2-0-1","label":"TXA","reference":"1-0-1","magnitude":"1","layer":2,"value_group":0}}}\n',
            encoding="utf-8",
        )
        vm = build_system_resource_workbench_view_model(data_root=root)
        names = {str(item.get("filename") or "") for item in list(vm.get("files") or [])}
        self.assertEqual(names, {"anthology.json", "samras-txa.json", "samras-msn.json"})
        self.assertTrue((root / "samras-txa.json").is_file())
        self.assertTrue((root / "samras-msn.json").is_file())
        lines = (root / "samras-txa.json").read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 3)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
