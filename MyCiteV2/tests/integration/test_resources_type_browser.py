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
    _build_extension_subtab_selector,
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
        # Manifest is folded into Browse — Browse is the unified default type tab.
        self.assertEqual(_resolve_inner_subtab("ext_resources", ""), "browse")
        self.assertEqual(_resolve_inner_subtab("ext_resources", "browse"), "browse")
        self.assertEqual(_resolve_inner_subtab("ext_resources", "bogus"), "browse")
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
        self.assertEqual([t["id"] for t in sel["tabs"]], ["browse", "per_grantee"])
        self.assertEqual(sel["selected_subtab"], "browse")
        by_id = {t["id"]: t["select_action"]["payload"]["surface_query"] for t in sel["tabs"]}
        self.assertEqual(by_id["browse"]["utilities_mode"], "global")
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
        self.assertEqual([t["id"] for t in sel["tabs"]], ["browse", "per_grantee"])

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

    def test_per_grantee_no_grantee_keeps_degraded_payload(self) -> None:
        # A timed-out/errored extension payload (degraded) must NOT be masked by the
        # generic prompt on the Per-grantee subtab — its `notice` is the only signal.
        extensions = [self._ext("ext_paypal", {"degraded": True, "notice": "PayPal did not respond within 5s"})]
        payload = _surface_payload_for_extensions(
            extensions=extensions, grantee_selector=None,
            selected_extension_tool_id="ext_paypal",
            extension_subtab="per_grantee", mode="global",
        )
        ep = payload["extensions"][0]["payload"]
        self.assertTrue(ep.get("degraded"))
        self.assertIn("did not respond", ep.get("notice", ""))
        self.assertNotIn("per_grantee_prompt", ep)

    def test_zero_operational_extensions_emits_empty_state_not_blank(self) -> None:
        # No operational extensions → emit a sections empty-state so the workbench
        # content probe still recognizes the surface (instead of a blank page).
        payload = _surface_payload_for_extensions(
            extensions=[], grantee_selector=None,
            selected_extension_tool_id="", mode="global",
        )
        self.assertNotIn("extensions", payload)
        self.assertTrue(payload.get("sections"))

    def test_between_extension_tab_preserves_active_subtab(self) -> None:
        # Switching the active extension must carry extension_subtab so the inner
        # Overall/Per-grantee highlight stays in sync with the content.
        sel = _build_extension_subtab_selector(
            [self._ext("ext_aws_email"), self._ext("ext_analytics")],
            "ext_aws_email",
            selected_grantee_msn="acme",
            utilities_mode="grantee",
            extension_subtab="per_grantee",
        )
        for tab in sel["tabs"]:
            self.assertEqual(
                tab["select_action"]["payload"]["surface_query"]["extension_subtab"],
                "per_grantee",
            )


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
            "function renderResourcesBrowse(",
            "function renderTypeIcon(",
            "function bindResourcesBrowse(",
            # Browse is the UNIFIED type tab (Manifest folded in): the cluster-tree
            # layout + render fns, the per-node "select for viewing" hook, and the
            # per-node icon-edit hook that replaces the old Manifest tab.
            "function clusterLayout(",
            "function renderDendrogram(",
            "data-open-type",
            "data-dendro-toggle",
            "data-edit-icon",
            "inner_subtab_selector",
            "<use href=",  # sprite icon rendering
        ):
            self.assertIn(token, self.js, token)

    def test_js_has_no_separate_manifest_tab(self) -> None:
        # The Manifest subtab is folded into Browse — its dedicated renderer/binder
        # must be gone so the two-tab regression can't quietly come back.
        for token in ("function renderResourcesManifest(", "function bindResourcesManifest("):
            self.assertNotIn(token, self.js, token)

    def test_css_has_theme_classes(self) -> None:
        for cls in (
            ".v2-innerSubtabs__option",
            ".v2-typeTree",
            ".v2-dendro",  # cluster-tree Browse hierarchy
            ".v2-leafletDir__search",  # searchable instance list
            ".v2-typeIcon",
        ):
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

    def test_browse_payload_carries_profile_edit_routes(self) -> None:
        # In-browse profile view/edit reuses the library detail+save endpoints,
        # so the Browse payload must stamp both routes for the instance viewer.
        p = self._browse(browse_view="hierarchy")
        self.assertEqual(p["profile_detail_route"], "/__fnd/resources/profile/detail")
        self.assertEqual(p["profile_save_route"], "/__fnd/resources/profile/save")

    def test_directory_profile_thumbnails_resolved(self) -> None:
        # A profile whose slug + a role token appear in an image filename gets a
        # thumbnail in the directory list; a profile with no matching image keeps
        # image_url == "" (the renderer shows the neutral dot placeholder). The
        # image is seeded here (not in _seed) so the shared count fixtures are
        # untouched.
        img = self.root / "clients" / "_shared" / "site-core" / "image"
        img.mkdir(parents=True, exist_ok=True)
        thumb = "0000-00-00.artifact-image.bloom_hill_farm.profile_headshot.avif"
        (img / thumb).write_text("x", encoding="utf-8")
        d = self._browse(browse_view="directory", browse_type="artifact-profile")
        rows = {r["slug"]: r for r in d["leaflets"]}
        self.assertEqual(rows["bloom_hill_farm"]["image_url"], "/assets/images/" + thumb)
        self.assertEqual(rows["nathan_seals"]["image_url"], "")

    def test_hierarchy_unaffected_by_thumbnail_resolution(self) -> None:
        # Thumbnails are a DIRECTORY-only concern — the hierarchy (dendrogram) payload
        # must not carry per-leaflet image_url (it renders type nodes, not instances).
        p = self._browse(browse_view="hierarchy")
        self.assertNotIn("leaflets", p)
        self.assertIn("nodes", p)

    def test_browse_hierarchy_carries_folded_in_manifest_capability(self) -> None:
        # The unified Browse hierarchy absorbs the Manifest registry: it must carry
        # the icon-edit routes + the rolled-up "Other (unregistered)" count so the
        # dendrogram can host per-node icon editing (there is no separate tab).
        p = self._browse(browse_view="hierarchy")
        self.assertEqual(p["set_icon_ref_route"], "/__fnd/resources/manifest/set-icon-ref")
        self.assertEqual(p["icon_options_route"], "/__fnd/resources/icon-options")
        self.assertIn("other_count", p)

    def test_render_ext_resources_defaults_to_browse(self) -> None:
        # Unknown / legacy 'manifest' subtab must resolve to the unified Browse tab,
        # never a now-removed manifest payload.
        for sub in ("", "manifest", "bogus"):
            ctx = {"webapps_root": self.root, "mode": "global", "extension_subtab": sub}
            self.assertEqual(rx._render_ext_resources(ctx)["resources_subtab"], "browse")


if __name__ == "__main__":
    unittest.main()
