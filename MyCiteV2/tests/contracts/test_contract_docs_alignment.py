from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ContractDocsAlignmentTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
