"""Phase 12e postcondition: the JS renderFormComponent dispatch case
remains wired in v2_portal_component_library.js's renderComponentFrame
switch and the renderer is exported on window.PortalComponentLibrary.

If a future cleanup commit accidentally deletes the `case "form":` arm
or the renderer export, every form-based extension (ext_grantee_profile
today, more in future phases) silently renders the "Unknown component
type" fallback. This test catches that class of regression at the
source level (no JS execution required).

Some of these assertions overlap with test_form_component_render_contract.py;
this file pins the *dispatch* specifically — the contract that the
switch statement recognizes the form type and the global is exported.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPONENT_LIBRARY_JS = (
    REPO_ROOT
    / "MyCiteV2"
    / "instances"
    / "_shared"
    / "portal_host"
    / "static"
    / "v2_portal_component_library.js"
)


class FormComponentDispatchPresentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = COMPONENT_LIBRARY_JS.read_text(encoding="utf-8")

    def test_render_component_frame_has_form_case(self) -> None:
        # The switch arm must route component_type "form" to
        # renderFormComponent. Match `case "form":` followed within a
        # few characters by the function call.
        self.assertRegex(
            self.source,
            r'case\s+"form"\s*:\s*\n?\s*return\s+renderFormComponent\(',
            "renderComponentFrame switch is missing the `case \"form\": "
            "return renderFormComponent(f);` arm. Form-based extensions "
            "(ext_grantee_profile and future) need this dispatch.",
        )

    def test_render_form_component_function_defined(self) -> None:
        self.assertRegex(
            self.source,
            r"function\s+renderFormComponent\s*\(",
            "renderFormComponent function not defined. Phase 7 introduced "
            "this primitive; deleting it breaks every form-based extension.",
        )

    def test_render_form_component_exported_on_window(self) -> None:
        # Look for the export inside window.PortalComponentLibrary = {...}.
        # Be tolerant of property ordering — just confirm the key:value pair.
        self.assertRegex(
            self.source,
            r"renderFormComponent\s*:\s*renderFormComponent",
            "renderFormComponent is not exported on "
            "window.PortalComponentLibrary. External callers (e.g., the "
            "tool palette JS) cannot discover the renderer without this.",
        )

    def test_render_form_field_supports_every_canonical_field_type(self) -> None:
        # renderFormField branches on field.type; each canonical type
        # produced by build_form_component_frame must have a JS branch.
        from MyCiteV2.packages.state_machine.nimm.mediate_handlers import FORM_FIELD_TYPES

        for field_type in FORM_FIELD_TYPES:
            # Type names appear as JS string literals in conditional
            # branches (e.g., `fieldType === "boolean"`). A bare grep
            # would match comments too; require quote-delimited usage.
            pattern = re.compile(rf'"{re.escape(field_type)}"')
            self.assertTrue(
                pattern.search(self.source),
                f"renderFormField has no visible branch for field type {field_type!r}. "
                "If a Python form passes this type, the JS renderer falls "
                "back to a generic text input, losing semantics.",
            )


if __name__ == "__main__":
    unittest.main()
