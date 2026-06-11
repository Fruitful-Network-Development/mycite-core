"""The resources type-browser inner-subtab framework (shell-runtime wiring).

Pins: subtab resolution (manifest default / valid / invalid / none), the inner
subtab selector's select_action surface_query (extension_subtab + pinned
extension/grantee/mode), and that ``_surface_payload_for_extensions`` attaches an
``inner_subtab_selector`` only to the active extension that declares subtabs.
"""

from __future__ import annotations

import sys
import tempfile
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
from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    resources_extension as rx,
)
from MyCiteV2.tests.unit.test_resource_types import _seed


class InnerSubtabResolve(unittest.TestCase):
    def test_default_valid_invalid_none(self) -> None:
        self.assertEqual(_resolve_inner_subtab("ext_resources", ""), "manifest")
        self.assertEqual(_resolve_inner_subtab("ext_resources", "browse"), "browse")
        self.assertEqual(_resolve_inner_subtab("ext_resources", "bogus"), "manifest")
        # Every operational extension now declares subtabs, defaulting to Overall.
        self.assertEqual(_resolve_inner_subtab("ext_aws_email", "x"), "overall")
        self.assertEqual(_resolve_inner_subtab("ext_aws_email", "per_grantee"), "per_grantee")
        # A tool with no subtab declaration (e.g. the grantee-profile surface tool).
        self.assertEqual(_resolve_inner_subtab("ext_grantee_profile", "x"), "")


class InnerSubtabSelector(unittest.TestCase):
    def test_subtab_drives_mode(self) -> None:
        # The subtab is the mode switch: per_grantee -> grantee, anything else -> global.
        sel = _build_inner_subtab_selector(
            "ext_resources", "browse", selected_grantee_msn="acme", utilities_mode="grantee"
        )
        self.assertEqual([t["id"] for t in sel["tabs"]], ["manifest", "browse", "per_grantee"])
        self.assertEqual(sel["selected_subtab"], "browse")
        by_id = {t["id"]: t["select_action"]["payload"]["surface_query"] for t in sel["tabs"]}
        self.assertEqual(by_id["browse"]["utilities_mode"], "global")
        self.assertEqual(by_id["manifest"]["utilities_mode"], "global")
        self.assertEqual(by_id["per_grantee"]["utilities_mode"], "grantee")
        self.assertEqual(by_id["browse"]["extension_subtab"], "browse")
        self.assertEqual(by_id["browse"]["selected_extension_tool_id"], "ext_resources")
        self.assertEqual(by_id["browse"]["selected_grantee_msn"], "acme")

    def test_operational_extension_has_overall_pergrantee(self) -> None:
        sel = _build_inner_subtab_selector(
            "ext_aws_email", "overall", selected_grantee_msn="", utilities_mode="global"
        )
        self.assertEqual([t["id"] for t in sel["tabs"]], ["overall", "per_grantee"])
        self.assertTrue(next(t for t in sel["tabs"] if t["id"] == "overall")["active"])


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

    def test_operational_extension_gets_inner_selector_no_surface_selector(self) -> None:
        # Every operational extension now carries the inner subtab strip, and the
        # Extensions surface no longer hosts a top-level grantee selector.
        extensions = [self._ext("ext_aws_email", {"overall_roster": True})]
        payload = _surface_payload_for_extensions(
            extensions=extensions,
            grantee_selector={"selected_grantee_msn": "", "grantees": []},
            selected_extension_tool_id="ext_aws_email",
            extension_subtab="overall",
            mode="global",
        )
        sel = payload["extensions"][0]["payload"]["inner_subtab_selector"]
        self.assertEqual([t["id"] for t in sel["tabs"]], ["overall", "per_grantee"])
        self.assertNotIn("grantee_selector", payload)

    def test_per_grantee_subtab_no_grantee_shows_prompt_and_picker(self) -> None:
        def _entry(msn, label, overall):
            return {
                "msn_id": msn, "label": label, "is_overall": overall,
                "select_action": {
                    "route": "/portal/api/v2/shell",
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "payload": {
                        "requested_surface_id": "utilities.extensions",
                        "surface_query": {"selected_grantee_msn": msn, "utilities_mode": "grantee" if msn else "global"},
                    },
                },
            }
        gsel = {"label": "Grantee", "selected_grantee_msn": "", "mode": "global",
                "grantees": [_entry("", "All — Overall", True), _entry("acme", "Acme", False)]}
        extensions = [self._ext("ext_aws_email", {"overall_roster": True})]
        payload = _surface_payload_for_extensions(
            extensions=extensions, grantee_selector=gsel,
            selected_extension_tool_id="ext_aws_email",
            extension_subtab="per_grantee", mode="global",
        )
        ep = payload["extensions"][0]["payload"]
        # no grantee chosen → the overall roster is replaced by a prompt
        self.assertIn("per_grantee_prompt", ep)
        self.assertNotIn("overall_roster", ep)
        # the picker is hosted in-card, WITHOUT the synthetic "All — Overall" entry
        self.assertIn("grantee_picker", ep)
        self.assertTrue(all(not g.get("is_overall") for g in ep["grantee_picker"]["grantees"]))


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


class BrowsePayloadReviewFixes(unittest.TestCase):
    """Regression guards for the 4 adversarial-review findings."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        _seed(self.root)

    def tearDown(self) -> None:
        self._td.cleanup()

    def _browse(self, **q) -> dict:
        ctx = {
            "webapps_root": self.root,
            "mode": q.pop("mode", "global"),
            "grantee": q.pop("grantee", {}),
            "surface_query": q.pop("sq", {}),
            "extension_subtab": "browse",
        }
        ctx.update(q)
        return rx._resources_browse_payload(ctx)

    def test_high1_instance_viewer_by_leaflet_type_not_directory(self) -> None:
        # An icon opened from the ROOT 'artifact' directory must route to the
        # asset viewer (parsed leaflet type), not the directory node's generic.
        p = self._browse(
            browse_view="instance",
            browse_type="artifact",
            browse_instance="/assets/icons/0000-00-00.artifact-icon.mycite.crop.svg",
        )
        self.assertEqual(p["instance"]["viewer"], "asset")

    def test_high2_nav_base_query_pins_extension_and_subtab(self) -> None:
        nb = self._browse(browse_view="hierarchy")["nav_base_query"]
        self.assertEqual(nb["selected_extension_tool_id"], "ext_resources")
        self.assertEqual(nb["extension_subtab"], "browse")

    def test_med3_pii_never_listed_even_in_grantee_mode(self) -> None:
        p = self._browse(
            browse_view="hierarchy", mode="grantee", grantee={"msn_id": "x"}, sq={"selected_grantee_msn": "x"}
        )
        ev = next((n for n in p["nodes"] if n["full_slug"] == "artifact-event"), {})
        self.assertEqual(ev.get("count"), 0)
        d = self._browse(
            browse_view="directory", browse_type="artifact-event", mode="grantee", grantee={"msn_id": "x"}
        )
        self.assertEqual(d.get("leaflets"), [])

    def test_low4_fallthrough_view_is_hierarchy(self) -> None:
        p = self._browse(browse_view="directory", browse_type="")
        self.assertEqual(p["browse_view"], "hierarchy")
        self.assertIn("nodes", p)


if __name__ == "__main__":
    unittest.main()
