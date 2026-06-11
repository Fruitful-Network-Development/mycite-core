"""The resources type-browser inner-subtab framework (shell-runtime wiring).

Pins: subtab resolution (manifest default / valid / invalid / none), the inner
subtab selector's select_action surface_query (extension_subtab + pinned
extension/grantee/mode), and that ``_surface_payload_for_extensions`` attaches an
``inner_subtab_selector`` only to the active extension that declares subtabs.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_shell_runtime import (
    _build_inner_subtab_selector,
    _resolve_inner_subtab,
    _surface_payload_for_extensions,
)


class InnerSubtabResolve(unittest.TestCase):
    def test_default_valid_invalid_none(self) -> None:
        self.assertEqual(_resolve_inner_subtab("ext_resources", ""), "manifest")
        self.assertEqual(_resolve_inner_subtab("ext_resources", "browse"), "browse")
        self.assertEqual(_resolve_inner_subtab("ext_resources", "bogus"), "manifest")
        self.assertEqual(_resolve_inner_subtab("ext_aws_email", "x"), "")  # declares no subtabs


class InnerSubtabSelector(unittest.TestCase):
    def test_tabs_and_select_action(self) -> None:
        sel = _build_inner_subtab_selector(
            "ext_resources", "browse", selected_grantee_msn="acme", utilities_mode="grantee"
        )
        self.assertEqual([t["id"] for t in sel["tabs"]], ["manifest", "browse", "per_grantee"])
        self.assertEqual(sel["selected_subtab"], "browse")
        browse = next(t for t in sel["tabs"] if t["id"] == "browse")
        self.assertTrue(browse["active"])
        sq = browse["select_action"]["payload"]["surface_query"]
        self.assertEqual(sq["extension_subtab"], "browse")
        self.assertEqual(sq["selected_extension_tool_id"], "ext_resources")
        self.assertEqual(sq["selected_grantee_msn"], "acme")
        self.assertEqual(sq["utilities_mode"], "grantee")


class SurfaceAttachesInnerSelector(unittest.TestCase):
    @staticmethod
    def _ext(tool_id: str, payload: dict | None = None) -> dict:
        return {"tool_id": tool_id, "label": tool_id, "summary": "", "payload": payload or {}}

    def test_inner_selector_on_active_resources(self) -> None:
        extensions = [self._ext("ext_aws_email"), self._ext("ext_resources", {"resources_app": True})]
        payload = _surface_payload_for_extensions(
            extensions=extensions,
            grantee_selector=None,
            selected_extension_tool_id="ext_resources",
            extension_subtab="browse",
            mode="global",
        )
        active = payload["extensions"]
        self.assertEqual([e["tool_id"] for e in active], ["ext_resources"])
        sel = active[0]["payload"]["inner_subtab_selector"]
        self.assertEqual(sel["selected_subtab"], "browse")
        self.assertEqual([t["id"] for t in sel["tabs"]], ["manifest", "browse", "per_grantee"])

    def test_no_inner_selector_for_non_subtab_extension(self) -> None:
        extensions = [self._ext("ext_aws_email", {"configuration": {"label": "x"}})]
        payload = _surface_payload_for_extensions(
            extensions=extensions,
            grantee_selector=None,
            selected_extension_tool_id="ext_aws_email",
            mode="global",
        )
        self.assertNotIn("inner_subtab_selector", payload["extensions"][0]["payload"])


class TypeBrowserJsInvariants(unittest.TestCase):
    """The JS shell must define the type-browser renderers/binders + use the icon
    sprite, and the CSS must carry the theme classes (mirrors
    test_extension_subtab_invariants)."""

    def setUp(self) -> None:
        base = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"
        self.js = (base / "v2_portal_workbench_renderers.js").read_text(encoding="utf-8")
        self.css = (base / "portal.css").read_text(encoding="utf-8")

    def test_js_defines_renderers_and_binders(self) -> None:
        for token in (
            "function renderInnerSubtabs(",
            "function bindInnerSubtabs(",
            "function renderResourcesManifest(",
            "function renderResourcesBrowse(",
            "function renderTypeIcon(",
            "function bindResourcesBrowse(",
            "function bindResourcesManifest(",
            "inner_subtab_selector",
            "<use href=",  # sprite icon rendering
        ):
            self.assertIn(token, self.js, token)

    def test_css_has_theme_classes(self) -> None:
        for cls in (".v2-innerSubtabs__option", ".v2-typeTree", ".v2-browseGrid", ".v2-typeIcon"):
            self.assertIn(cls, self.css, cls)


if __name__ == "__main__":
    unittest.main()
