"""Phase 14a postcondition — extensions surface payloads must reach the DOM.

The Phase 12g/12h refactors made the surface payload's ``extensions`` list
the canonical channel for utilities-tab extension content. For most of
Phase 13 that list was emitted server-side but silently dropped by
``v2_portal_workbench_renderers.js::renderGenericSurface`` — only
``cards``, ``sections``, ``notes``, and ``grantee_selector`` got rendered.
Phase 14a closes that gap.

These tests pin the JS-side contract so the gap can't re-open: when the
renderer is edited or refactored, the postcondition fails if any of the
load-bearing helpers go missing.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WORKBENCH_JS = (
    Path(__file__).resolve().parents[2]
    / "instances"
    / "_shared"
    / "portal_host"
    / "static"
    / "v2_portal_workbench_renderers.js"
)


class ExtensionPayloadRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = WORKBENCH_JS.read_text(encoding="utf-8")

    def test_render_extensions_function_defined(self) -> None:
        self.assertIn("function renderExtensions(", self.source)

    def test_render_extension_card_body_function_defined(self) -> None:
        # Card body is the dispatch-by-shape helper. If it disappears the
        # extensions surface will go silently blank for ext_aws_email +
        # ext_paypal + ext_analytics + ext_newsletter.
        self.assertIn("function renderExtensionCardBody(", self.source)

    def test_bind_extension_actions_function_defined(self) -> None:
        self.assertIn("function bindExtensionActions(", self.source)

    def test_bind_form_submit_function_defined(self) -> None:
        # The Phase 9 grantee form scaffold rendered the <form> but
        # nothing wired the submit. Phase 14a added this; if it goes
        # away, the grantee form silently no-ops.
        self.assertIn("function bindFormSubmit(", self.source)

    def test_generic_surface_renders_extensions(self) -> None:
        self.assertIn("renderExtensions(extensions)", self.source)

    def test_generic_surface_binds_extension_actions(self) -> None:
        self.assertIn("bindExtensionActions(ctx, target, extensions)", self.source)

    def test_form_submit_uses_fetch_post(self) -> None:
        # Catch refactor regressions where the POST shape might change
        # to something the route handler can't decode.
        self.assertIn('method: "POST"', self.source)
        self.assertIn('data-form-submit-route', self.source)


if __name__ == "__main__":
    unittest.main()
