"""Phase 12h postcondition: the workbench renderer JS must include the
grantee_selector rendering + binding helpers.

The surface payload carries `grantee_selector` for the utilities tab; if
the JS forgets to render it, the operator can't switch grantees. This
test pins the two helpers' presence so accidental deletion fails CI.
"""

from __future__ import annotations

import unittest
from pathlib import Path

WORKBENCH_JS = (
    Path(__file__).resolve().parents[2]
    / "instances"
    / "_shared"
    / "portal_host"
    / "static"
    / "v2_portal_workbench_renderers.js"
)


class WorkbenchGranteeSelectorRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = WORKBENCH_JS.read_text(encoding="utf-8")

    def test_render_grantee_selector_function_defined(self) -> None:
        self.assertIn("function renderGranteeSelector(", self.source)

    def test_bind_grantee_selector_function_defined(self) -> None:
        self.assertIn("function bindGranteeSelector(", self.source)

    def test_generic_surface_renders_selector_at_top(self) -> None:
        marker = "renderGranteeSelector(granteeSelector)"
        self.assertIn(marker, self.source)

    def test_generic_surface_binds_selector_after_render(self) -> None:
        self.assertIn("bindGranteeSelector(ctx, target, granteeSelector)", self.source)

    def test_selector_dispatches_via_loadshell(self) -> None:
        self.assertIn("ctx.loadShell(payload)", self.source)


if __name__ == "__main__":
    unittest.main()
