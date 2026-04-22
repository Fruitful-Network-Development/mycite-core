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
            "docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md",
            "docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md",
            "docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md",
            "docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md",
            "docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md",
            "docs/audits/reports/mos_premorice_and_modularization_posture_report_2026-04-22.md",
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
            "docs/audits/reports/cts_gis_sql_authority_assurance_report_2026-04-21.md",
            "docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md",
            "docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md",
            "docs/audits/reports/mos_system_surface_visualization_reflectivity_report_2026-04-22.md",
            "docs/audits/reports/mos_cutover_intent_integrity_report_2026-04-22.md",
            "docs/audits/reports/mos_premorice_and_modularization_posture_report_2026-04-22.md",
            "docs/audits/reports/workbench_ui_utilitarian_design_audit_2026-04-21.md",
            "docs/plans/mos_post_closure_consolidation_plan_2026-04-21.md",
            "docs/plans/mos_novelty_positioning_follow_on_2026-04-21.md",
            "docs/plans/workbench_ui_hardening_follow_on_2026-04-21.md",
        ):
            self.assertIn(f"| `{relative_path}` |", checklist_text)

    def test_active_docs_do_not_treat_personal_note_master_plan_as_canonical(self) -> None:
        stale_basename = "mos_" + "master_plan.md"
        allowed_historical_context = {
            "docs/audits/reports/mos_personal_notes_to_canon_crosswalk_2026-04-21.md",
            "docs/audits/reports/mos_documentation_supersession_audit_2026-04-21.md",
            "docs/audits/reports/mos_program_closure_audit_checklist_2026-04-21.md",
        }
        for path in (REPO_ROOT / "docs").rglob("*.md"):
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            if relative_path.startswith("docs/personal_notes/"):
                continue
            text = _read_text(path)
            if stale_basename not in text:
                continue
            if relative_path in allowed_historical_context:
                lowered = text.lower()
                self.assertTrue("archived" in lowered or "source-only" in lowered, relative_path)
                self.assertIn("docs/plans/master_plan_mos.md", text, relative_path)
                continue
            self.fail(relative_path)

    def test_retired_mos_source_notes_are_archived_and_crosswalked(self) -> None:
        archived = {
            "docs/personal_notes/archive/MOS/cuttover_consideration.md",
            "docs/personal_notes/archive/MOS/datum_logic_area_investigation_clarity.md",
            "docs/personal_notes/archive/MOS/mos_master_plan.md",
        }
        for relative_path in archived:
            self.assertTrue((REPO_ROOT / relative_path).is_file(), relative_path)

        self.assertFalse((REPO_ROOT / "docs/personal_notes/MOS/cuttover_consideration.md").exists())
        self.assertFalse((REPO_ROOT / "docs/personal_notes/MOS/datum_logic_area_investigation_clarity.md").exists())
        self.assertFalse((REPO_ROOT / "docs/personal_notes/MOS/mos_master_plan.md").exists())

        crosswalk_text = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "mos_personal_notes_to_canon_crosswalk_2026-04-21.md"
        )
        for relative_path in archived:
            self.assertIn(relative_path, crosswalk_text)

    def test_readmes_reference_post_closure_mos_follow_on_docs(self) -> None:
        plans_readme = _read_text(REPO_ROOT / "docs" / "plans" / "README.md")
        audits_readme = _read_text(REPO_ROOT / "docs" / "audits" / "README.md")

        self.assertIn("cts_gis_sql_authority_assurance_report_2026-04-21.md", plans_readme)
        self.assertIn("mos_system_surface_visualization_reflectivity_report_2026-04-22.md", plans_readme)
        self.assertIn("mos_cutover_intent_integrity_report_2026-04-22.md", plans_readme)
        self.assertIn("mos_premorice_and_modularization_posture_report_2026-04-22.md", plans_readme)
        self.assertIn("mos_post_closure_consolidation_plan_2026-04-21.md", plans_readme)
        self.assertIn("mos_novelty_positioning_follow_on_2026-04-21.md", plans_readme)
        self.assertIn("workbench_ui_hardening_follow_on_2026-04-21.md", plans_readme)
        self.assertIn("cts_gis_sql_authority_assurance_report_2026-04-21.md", audits_readme)
        self.assertIn("mos_personal_notes_to_canon_crosswalk_2026-04-21.md", audits_readme)
        self.assertIn("mos_documentation_supersession_audit_2026-04-21.md", audits_readme)
        self.assertIn("mos_system_surface_visualization_reflectivity_report_2026-04-22.md", audits_readme)
        self.assertIn("mos_cutover_intent_integrity_report_2026-04-22.md", audits_readme)
        self.assertIn("mos_premorice_and_modularization_posture_report_2026-04-22.md", audits_readme)
        self.assertIn("workbench_ui_utilitarian_design_audit_2026-04-21.md", audits_readme)

    def test_mos_reflectivity_follow_on_audits_are_closed_by_reports(self) -> None:
        active_plan_paths = [
            REPO_ROOT / "docs" / "audits" / "mos_system_surface_visualization_reflectivity_audit_plan_2026-04-21.md",
            REPO_ROOT / "docs" / "audits" / "mos_cutover_intent_integrity_audit_plan_2026-04-21.md",
            REPO_ROOT / "docs" / "audits" / "mos_premorice_and_modularization_posture_audit_plan_2026-04-21.md",
        ]
        for path in active_plan_paths:
            text = _read_text(path)
            self.assertIn("Lifecycle: `completed`", text, path.relative_to(REPO_ROOT).as_posix())
            self.assertIn("2026-04-22.md", text, path.relative_to(REPO_ROOT).as_posix())

        reality_report = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "mos_runtime_authority_and_access_reality_report_2026-04-21.md"
        )
        self.assertIn("closed on 2026-04-22", reality_report)
        self.assertIn("mos_system_surface_visualization_reflectivity_report_2026-04-22.md", reality_report)
        self.assertIn("mos_cutover_intent_integrity_report_2026-04-22.md", reality_report)
        self.assertIn("mos_premorice_and_modularization_posture_report_2026-04-22.md", reality_report)

    def test_cts_gis_sql_authority_assurance_report_records_gate_and_counts(self) -> None:
        report_text = _read_text(
            REPO_ROOT / "docs" / "audits" / "reports" / "cts_gis_sql_authority_assurance_report_2026-04-21.md"
        )

        self.assertIn("409", report_text)
        self.assertIn("3133", report_text)
        self.assertIn("406", report_text)
        self.assertIn("2233", report_text)
        self.assertIn("no missing local references", report_text)
        self.assertIn("no row warnings", report_text)
        self.assertIn("3-2-3-17-77-1-14", report_text)
        self.assertIn("blocked", report_text)


if __name__ == "__main__":
    unittest.main()
