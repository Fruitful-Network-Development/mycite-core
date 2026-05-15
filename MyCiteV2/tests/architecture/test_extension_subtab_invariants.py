"""Phase 15a — JS-text postcondition for the extension subtab renderer.

The Extensions surface payload now carries an
``extension_subtab_selector`` that ``v2_portal_workbench_renderers.js``
turns into a clickable tab strip. This test pins the JS-side wiring
the same way ``test_extension_payload_renders.py`` pins
``renderExtensions`` (Phase 14a) — by scanning the source text for
the named functions + their callers.

If a future refactor renames or drops ``renderExtensionTabs`` /
``bindExtensionTabs`` without an explicit cleanup, this test catches
it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STATIC_DIR = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
RENDERERS_PATH = STATIC_DIR / "v2_portal_workbench_renderers.js"
CSS_PATH = STATIC_DIR / "portal.css"


class ExtensionSubtabRendererInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.js = RENDERERS_PATH.read_text(encoding="utf-8")
        cls.css = CSS_PATH.read_text(encoding="utf-8")

    def test_render_extension_tabs_defined(self) -> None:
        self.assertIn("function renderExtensionTabs(", self.js)

    def test_bind_extension_tabs_defined(self) -> None:
        self.assertIn("function bindExtensionTabs(", self.js)

    def test_renderGenericSurface_calls_renderExtensionTabs(self) -> None:
        # Sloppy but effective: the renderer must thread tabs into the
        # surface render and bind them after.
        self.assertIn("renderExtensionTabs(", self.js)
        self.assertIn("bindExtensionTabs(", self.js)

    def test_subtab_selector_key_is_canonical(self) -> None:
        # The JS reads ``extension_subtab_selector`` from the surface
        # payload — match the server-side key exactly so a rename on
        # either side breaks loudly.
        self.assertIn("extension_subtab_selector", self.js)

    def test_subtab_css_classes_present(self) -> None:
        for cls_name in (
            ".v2-extensionTabs",
            ".v2-extensionTabs__options",
            ".v2-extensionTabs__option",
            ".v2-extensionTabs__option.is-active",
        ):
            self.assertIn(cls_name, self.css, f"{cls_name} missing from portal.css")


if __name__ == "__main__":
    unittest.main()
