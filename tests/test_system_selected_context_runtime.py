from __future__ import annotations

import unittest

from _shared.portal.application.shell.runtime import build_selected_context_payload
from _shared.portal.application.workbench.document_contract import build_workbench_document


class SystemSelectedContextRuntimeTests(unittest.TestCase):
    def test_file_focus_exposes_system_state_and_aitas_level_one(self) -> None:
        document = build_workbench_document(
            document_id="workbench:system:anthology",
            instance_id="fnd",
            logical_key="anthology",
            display_name="anthology.json",
            family_kind="resource",
            family_type="anthology",
            family_subtype="json",
            scope_kind="local",
            payload={"file_key": "anthology", "filename": "anthology.json"},
        )

        payload = build_selected_context_payload(document=document, shell_verb="navigate")
        system_state = payload.get("system_state") or {}
        aitas = system_state.get("aitas") or {}

        self.assertEqual(system_state.get("focus_kind"), "file")
        self.assertEqual(system_state.get("active_file_key"), "anthology")
        self.assertEqual(system_state.get("active_filename"), "anthology.json")
        self.assertEqual(system_state.get("active_directive"), "navigate")
        self.assertEqual(((aitas.get("attention") or {}).get("value")), "anthology.json")
        self.assertEqual(((aitas.get("intention") or {}).get("value")), "navigate")
        self.assertEqual(((aitas.get("archetype") or {}).get("value")), "null")
        self.assertEqual(((aitas.get("spacial") or {}).get("value")), 1)

    def test_datum_focus_exposes_system_state_and_aitas_level_two(self) -> None:
        document = build_workbench_document(
            document_id="workbench:system:txa",
            instance_id="fnd",
            logical_key="txa",
            display_name="samras-txa.json",
            family_kind="resource",
            family_type="samras_txa",
            family_subtype="txa",
            scope_kind="local",
            payload={"file_key": "txa", "filename": "samras-txa.json"},
        )

        payload = build_selected_context_payload(
            document=document,
            selected_row={"identifier": "8-5-11", "label": "Product Type", "file_key": "txa"},
            shell_verb="mediate",
        )
        system_state = payload.get("system_state") or {}
        aitas = system_state.get("aitas") or {}

        self.assertEqual(system_state.get("focus_kind"), "datum")
        self.assertEqual(system_state.get("active_file_key"), "txa")
        self.assertEqual(system_state.get("selected_datum_id"), "8-5-11")
        self.assertEqual(system_state.get("selected_datum_label"), "Product Type")
        self.assertEqual(system_state.get("active_directive"), "mediate")
        self.assertEqual(((aitas.get("attention") or {}).get("value")), "8-5-11")
        self.assertEqual(((aitas.get("intention") or {}).get("value")), "mediate")
        self.assertEqual(((aitas.get("archetype") or {}).get("kind")), "resolved")
        self.assertEqual(((aitas.get("archetype") or {}).get("value")), "taxonomy")
        self.assertEqual(((aitas.get("spacial") or {}).get("value")), 2)


if __name__ == "__main__":
    unittest.main()
