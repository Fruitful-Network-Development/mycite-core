"""Tests for TXA sandbox workspace view-model helpers (title table + branch preview)."""

from __future__ import annotations

import unittest

from _shared.portal.sandbox.txa_sandbox_workspace import (
    build_branch_context,
    build_samras_workspace_view_model,
    build_title_table_rows,
    build_txa_sandbox_view_model,
    normalize_staged_entries,
    samras_next_child_address,
    samras_parent_address,
)


class TxaSandboxWorkspaceTests(unittest.TestCase):
    def test_parent_and_next_child_asparagus_style_branch(self):
        """One child under parent ...-1 → next child is ...-2."""
        parent = "1-1-3-3-5-6-7-2-1-1-1"
        rows = [
            {"address_id": parent, "title": "asparagus_officinalis"},
            {"address_id": "1-1-3-3-5-6-7-2-1-1-1-1", "title": "mary_washington"},
        ]
        self.assertEqual(samras_parent_address("1-1-3-3-5-6-7-2-1-1-1-1"), parent)
        self.assertEqual(samras_next_child_address(parent, rows), "1-1-3-3-5-6-7-2-1-1-1-2")

    def test_normalize_staged_assigns_next_child(self):
        persisted = [{"address_id": "1-1", "title": "species"}]
        staged = [{"parent_address": "1-1", "title": "purple_passion"}]
        norm, warnings = normalize_staged_entries(persisted, staged)
        self.assertFalse(warnings)
        self.assertEqual(len(norm), 1)
        self.assertEqual(norm[0]["provisional_child_address"], "1-1-1")

    def test_build_txa_sandbox_view_model_merges_staged(self):
        resource = {
            "resource_id": "txa.demo",
            "resource_kind": "samras",
            "rows_by_address": {
                "1-1-3-3-5-6-7-2-1-1-1": ["asparagus_officinalis"],
                "1-1-3-3-5-6-7-2-1-1-1-1": ["mary_washington"],
            },
        }
        parent = "1-1-3-3-5-6-7-2-1-1-1"
        vm = build_txa_sandbox_view_model(
            resource,
            selected_address_id=parent,
            staged_entries=[{"parent_address": parent, "title": "purple_passion"}],
        )
        self.assertTrue(vm.get("title_table_rows"))
        ids = [r["address_id"] for r in vm["title_table_rows"]]
        self.assertIn("1-1-3-3-5-6-7-2-1-1-1-2", ids)
        staged_rows = [r for r in vm["title_table_rows"] if r.get("status") == "staged"]
        self.assertEqual(len(staged_rows), 1)
        self.assertEqual(staged_rows[0]["title"], "purple_passion")
        bc = vm.get("branch_context") or {}
        # mary at …-1 + staged purple at …-2 → next free slot is …-3
        self.assertEqual(bc.get("next_child_preview"), "1-1-3-3-5-6-7-2-1-1-1-3")

    def test_next_child_single_existing_child(self):
        parent = "1-1-3-3-5-6-7-2-1-1-1"
        rows = [
            {"address_id": parent, "title": "asparagus_officinalis"},
            {"address_id": "1-1-3-3-5-6-7-2-1-1-1-1", "title": "mary_washington"},
        ]
        self.assertEqual(samras_next_child_address(parent, rows), "1-1-3-3-5-6-7-2-1-1-1-2")

    def test_branch_context_siblings(self):
        rows = [
            {"address_id": "1-1-1", "title": "a"},
            {"address_id": "1-1-2", "title": "b"},
        ]
        bc = build_branch_context("1-1-1", rows)
        self.assertEqual(len(bc["siblings"]), 2)

    def test_build_samras_workspace_view_model_includes_structural_detail(self):
        resource = {
            "resource_id": "msn.demo",
            "resource_kind": "msn",
            "rows_by_address": {"1": ["R"], "1-1": ["C"]},
        }
        vm = build_samras_workspace_view_model(resource, selected_address_id="1-1", staged_entries=[])
        detail = vm.get("structural_detail") if isinstance(vm.get("structural_detail"), dict) else {}
        self.assertEqual(detail.get("schema"), "mycite.portal.samras.structural_detail.v1")
        self.assertEqual(detail.get("selected_address_id"), "1-1")


if __name__ == "__main__":
    unittest.main()
