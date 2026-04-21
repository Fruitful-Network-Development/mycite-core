from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class MosPostClosureDocsTests(unittest.TestCase):
    def test_post_closure_follow_on_artifacts_exist(self) -> None:
        expected = {
            "docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md",
            "docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md",
            "docs/audits/reports/workbench_ui_utilitarian_design_audit_2026-04-21.md",
            "docs/plans/mos_post_closure_consolidation_plan_2026-04-21.md",
            "docs/plans/mos_novelty_positioning_follow_on_2026-04-21.md",
            "docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md",
        }
        for relative_path in expected:
            self.assertTrue((REPO_ROOT / relative_path).is_file(), relative_path)

    def test_closure_checklist_covers_post_closure_artifacts(self) -> None:
        checklist_text = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "mos_program_closure_audit_checklist_2026-04-21.md"
        )
        for relative_path in (
            "docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md",
            "docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md",
            "docs/audits/reports/workbench_ui_utilitarian_design_audit_2026-04-21.md",
            "docs/plans/mos_post_closure_consolidation_plan_2026-04-21.md",
            "docs/plans/mos_novelty_positioning_follow_on_2026-04-21.md",
            "docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md",
        ):
            self.assertIn(f"| `{relative_path}` |", checklist_text)

    def test_docs_do_not_reference_stale_personal_note_master_plan_basename(self) -> None:
        stale_basename = "mos_" + "master_plan.md"
        for path in (REPO_ROOT / "docs").rglob("*.md"):
            self.assertNotIn(stale_basename, _read_text(path), path.relative_to(REPO_ROOT).as_posix())

    def test_readmes_reference_post_closure_mos_follow_on_docs(self) -> None:
        plans_readme = _read_text(REPO_ROOT / "docs" / "plans" / "README.md")
        audits_readme = _read_text(REPO_ROOT / "docs" / "audits" / "README.md")

        self.assertIn("mos_post_closure_consolidation_plan_2026-04-21.md", plans_readme)
        self.assertIn("mos_novelty_positioning_follow_on_2026-04-21.md", plans_readme)
        self.assertIn("workbench_ui_hardening_follow_on_2026-04-21.md", plans_readme)
        self.assertIn("mos_personal_notes_to_canon_crosswalk_2026-04-21.md", audits_readme)
        self.assertIn("mos_documentation_supersession_audit_2026-04-21.md", audits_readme)
        self.assertIn("workbench_ui_utilitarian_design_audit_2026-04-21.md", audits_readme)


if __name__ == "__main__":
    unittest.main()
