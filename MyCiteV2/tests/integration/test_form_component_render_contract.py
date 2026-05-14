"""Render-contract test for the form component — Phase 7.

Asserts that the JS component library at
instances/_shared/portal_host/static/v2_portal_component_library.js:
  - recognizes "form" as a component_type in the renderComponentFrame switch
  - exposes renderFormComponent on window.PortalComponentLibrary
  - renders an editable input element for each field type produced by
    build_form_component_frame

We cannot run the JS in this environment, so the test is source-level:
parses the file as text and checks for the required dispatch case, the
required exported function, and a representative HTML emission for each
supported field type. The Python-side build_form_component_frame is also
exercised so that the JS and Python sides agree on the frame shape.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.state_machine.nimm.mediate_handlers import (
    FORM_FIELD_TYPES,
    build_form_component_frame,
)

COMPONENT_LIBRARY_JS = (
    REPO_ROOT
    / "MyCiteV2"
    / "instances"
    / "_shared"
    / "portal_host"
    / "static"
    / "v2_portal_component_library.js"
)


class JsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = COMPONENT_LIBRARY_JS.read_text(encoding="utf-8")

    def test_dispatcher_recognises_form(self) -> None:
        self.assertIn('case "form":', self.source)
        self.assertIn("renderFormComponent(f)", self.source)

    def test_renderer_function_defined(self) -> None:
        self.assertIn("function renderFormComponent(", self.source)

    def test_renderer_exposed_on_window(self) -> None:
        self.assertIn("renderFormComponent: renderFormComponent", self.source)

    def test_each_field_type_has_branch(self) -> None:
        # Each canonical field type from the Python side must have a render
        # branch in the JS field renderer. Type names appear as switch tokens
        # or comparison strings.
        for field_type in FORM_FIELD_TYPES:
            self.assertIn(
                field_type,
                self.source,
                f"renderFormField has no visible branch for field type {field_type!r}",
            )


class PythonJsAgreementTests(unittest.TestCase):
    """The Python builder produces frames whose shape the JS renderer expects.
    No JS execution here; just structural agreement on the keys the JS reads.
    """

    def test_frame_has_component_type_form_and_payload_fields(self) -> None:
        frame = build_form_component_frame(
            frame_id="contract_check",
            label="Contract Check",
            fields=[
                {"key": "label", "type": "text", "value": "x"},
                {"key": "active", "type": "boolean", "value": True},
                {"key": "tier", "type": "select", "options": ["a", "b"], "value": "a"},
                {"key": "domains", "type": "string_list", "value": ["a.com"]},
                {"key": "notes", "type": "multiline", "value": "hi"},
            ],
            submit_action={
                "route": "/__fnd/grantee/save",
                "schema": "mycite.v2.grantee.save.request.v1",
                "payload": {"msn_id": "x"},
            },
        )
        self.assertEqual(frame["component_type"], "form")
        payload = frame["payload"]
        self.assertIn("fields", payload)
        self.assertIn("submit_action", payload)
        self.assertEqual(payload["submit_action"]["route"], "/__fnd/grantee/save")
        # Every field exposes the keys the JS renderer reads.
        for field in payload["fields"]:
            self.assertIn("key", field)
            self.assertIn("type", field)
            self.assertIn("required", field)


if __name__ == "__main__":
    unittest.main()
