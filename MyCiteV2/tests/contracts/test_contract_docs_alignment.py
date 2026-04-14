from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ContractDocsAlignmentTests(unittest.TestCase):
    def test_admin_shell_region_doc_lists_posture_and_boot_state_tokens(self) -> None:
        text = (REPO_ROOT / "docs" / "contracts" / "shell_region_kinds.md").read_text(
            encoding="utf-8"
        )

        for token in (
            "tool_collapsed_inspector",
            "surface_posture",
            "interface-panel",
            "data-shell-boot-state",
            "primary_surface",
            "layout_mode",
        ):
            self.assertIn(token, text)

    def test_trusted_tenant_shell_region_doc_lists_current_runtime_kinds(self) -> None:
        text = (
            REPO_ROOT / "docs" / "contracts" / "trusted_tenant_shell_region_kinds.md"
        ).read_text(encoding="utf-8")

        for token in (
            "tenant_home_status",
            "operational_status",
            "audit_activity",
            "profile_basics_write",
            "tenant_profile_summary",
            "operational_status_summary",
            "audit_activity_summary",
            "profile_basics_write_summary",
        ):
            self.assertIn(token, text)

    def test_datum_io_doc_lists_required_diagnostics_and_source_boundaries(self) -> None:
        text = (REPO_ROOT / "docs" / "contracts" / "datum_io_and_recognition.md").read_text(
            encoding="utf-8"
        )

        for token in (
            "data/system/anthology.json",
            "data/sandbox/<tool>/sources/*.json",
            "rf.<datum_address>",
            "illegal_magnitude_literal",
            "address_irregularity",
            "unrecognized_family",
        ):
            self.assertIn(token, text)

    def test_network_docs_keep_read_only_contract_first_v2_language(self) -> None:
        current_text = "\n".join(
            (
                (REPO_ROOT / "docs" / "contracts" / "admin_network_root_read_model.md").read_text(encoding="utf-8"),
                (REPO_ROOT / "docs" / "contracts" / "network_operation_and_p2p_boundary.md").read_text(encoding="utf-8"),
                (REPO_ROOT / "docs" / "plans" / "post_mvp_rollout" / "current_planning_index.md").read_text(encoding="utf-8"),
                (REPO_ROOT / "docs" / "audits" / "v2_network_v1_to_v2_crosswalk_audit_2026-04-14.md").read_text(encoding="utf-8"),
            )
        )

        for token in (
            "read-only",
            "contract-first",
            "host_alias_tool",
            "tenant_progeny_profiles",
            "active_service=network",
            "workbench_kind=network_root",
            "contract_first_read_model",
        ):
            self.assertIn(token, current_text)

        for legacy_phrase in (
            "NETWORK > Contracts is the canonical contract editor",
            "profile editing, and contract context",
            "/portal/api/data/write/field_contracts",
        ):
            self.assertNotIn(legacy_phrase, current_text)

    def test_tool_taxonomy_docs_keep_default_tool_forbidden(self) -> None:
        text = "\n".join(
            (
                (REPO_ROOT / "docs" / "contracts" / "tool_kind_and_portal_attachment_contract.md").read_text(encoding="utf-8"),
                (REPO_ROOT / "docs" / "contracts" / "tool_exposure_and_admin_activity_bar_contract.md").read_text(encoding="utf-8"),
            )
        )

        self.assertIn("default_tool", text)
        self.assertIn("forbidden", text)


if __name__ == "__main__":
    unittest.main()
