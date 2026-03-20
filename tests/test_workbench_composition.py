"""Tests for shared workbench composition helpers."""

from __future__ import annotations

import unittest

from _shared.portal.workbench.workbench_composition import build_grouped_workbench_bundle
from _shared.portal.workbench.samras_structural_detail import build_samras_structural_detail_vm


class WorkbenchCompositionTests(unittest.TestCase):
    def test_grouped_bundle_flattens_layers_and_value_groups(self):
        table_view = {
            "table": {"table_id": "anthology", "title": "Anthology", "row_count": 2},
            "layers": [
                {
                    "layer": 1,
                    "row_count": 2,
                    "value_groups": [
                        {
                            "value_group": 0,
                            "row_count": 1,
                            "rows": [{"identifier": "1-1-1", "layer": 1, "value_group": 0}],
                        },
                        {
                            "value_group": 1,
                            "row_count": 1,
                            "rows": [{"identifier": "1-1-2", "layer": 1, "value_group": 1}],
                        },
                    ],
                }
            ],
            "rows": [{"identifier": "1-1-1"}, {"identifier": "1-1-2"}],
            "warnings": [],
        }
        bundle = build_grouped_workbench_bundle(table_view)
        self.assertEqual(bundle.get("schema"), "mycite.portal.workbench.grouped_bundle.v1")
        self.assertEqual(bundle.get("row_count"), 2)
        bands = bundle.get("bands") or []
        self.assertEqual(len(bands), 1)
        vgs = bands[0].get("value_groups") or []
        self.assertEqual(len(vgs), 2)
        self.assertEqual(vgs[0].get("family_key"), "L1::VG0")


class SamrasStructuralDetailTests(unittest.TestCase):
    def test_structural_detail_includes_levels_and_staged_preview(self):
        branch = {
            "selected_address_id": "1-1",
            "parent_address": "1",
            "path_to_root": ["1", "1-1"],
            "siblings": [{"address_id": "1-1", "title": "a", "is_selected": True}],
            "children": [],
            "next_child_preview": "1-1-1",
            "child_count": 0,
            "sibling_index": 0,
        }
        staged = [{"parent_address": "1-1", "provisional_child_address": "1-1-1", "title": "staged_leaf"}]
        vm = build_samras_structural_detail_vm(branch, normalized_staged_entries=staged)
        self.assertEqual(vm.get("schema"), "mycite.portal.samras.structural_detail.v1")
        self.assertEqual(vm.get("next_child_preview"), "1-1-1")
        self.assertTrue(any((lvl.get("key") == "siblings") for lvl in (vm.get("levels") or [])))
        prev = vm.get("staged_structural_preview") or []
        self.assertEqual(len(prev), 1)
        self.assertEqual(prev[0].get("title"), "staged_leaf")


if __name__ == "__main__":
    unittest.main()
