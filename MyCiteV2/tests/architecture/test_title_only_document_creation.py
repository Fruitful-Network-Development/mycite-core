"""Stage 3b postcondition: the human-facing new-document create flow is
title-only and posts operation=create_document.

Implementation templates (product_profile, agro_erp_taxonomy_source, ...)
must not leak into the create gate, and the JS must post the
``create_document`` operation that the mutation runtime allowlists. This
pins both at the source level (no JS execution harness exists), so a future
edit cannot silently reintroduce the template picker or revert the operation
to scaffold_datum (which would make creation ask for a profile/type again).
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STATIC = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
WORKBENCH_JS = STATIC / "v2_portal_workbench_renderers.js"
REGION_JS = STATIC / "v2_portal_shell_region_renderers.js"


class TitleOnlyDocumentCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workbench = WORKBENCH_JS.read_text(encoding="utf-8")
        cls.region = REGION_JS.read_text(encoding="utf-8")

    def test_create_forms_post_create_document_operation(self) -> None:
        self.assertIn('operation: "create_document"', self.workbench)
        self.assertIn('payload.operation = "create_document"', self.region)

    def test_create_forms_do_not_post_a_template_id(self) -> None:
        # The template/type selection must not be part of the create payload.
        self.assertNotIn("template_id", self.workbench)
        self.assertNotIn("template_id", self.region)

    def test_create_forms_render_no_template_picker(self) -> None:
        for source in (self.workbench, self.region):
            self.assertNotIn('data-role="template-select"', source)
            self.assertNotIn("available_templates", source)


if __name__ == "__main__":
    unittest.main()
