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

from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    resources_extension as rx,
)
from MyCiteV2.tests.unit.test_resource_types import _seed


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

    def test_directory_logo_ref_fallback_resolves_thumbnail(self) -> None:
        # A profile whose registered slug (akron_microgreens_llc) is NOT a substring
        # of its logo's stem (akron_microgreens) is missed by the cheap slug+role
        # match, but its explicit logo_ref still resolves the thumbnail in the
        # directory list (the legal-name-enrichment slug/stem-mismatch case).
        sc = self.root / "clients" / "_shared" / "site-core"
        (sc / "profiles" / "0000-00-00.artifact-profile-legal_entity-ag-producer-crop.akron_microgreens_llc.profile.yaml").write_text(
            "display_name: Akron Microgreens\nlogo_ref: 0000-00-00.artifact-logo.akron_microgreens.logo\n",
            encoding="utf-8",
        )
        img = sc / "image"
        img.mkdir(parents=True, exist_ok=True)
        logo = "0000-00-00.artifact-logo.akron_microgreens.logo.avif"
        (img / logo).write_text("x", encoding="utf-8")
        d = self._browse(browse_view="directory", browse_type="artifact-profile")
        rows = {r["slug"]: r for r in d["leaflets"]}
        self.assertEqual(rows["akron_microgreens_llc"]["image_url"], "/assets/images/" + logo)

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

    def test_browse_payload_unknown_subtab_resolves_to_browse(self) -> None:
        # The dissolved ext_resources renderer routed unknown / legacy 'manifest'
        # subtabs to the unified Browse tab; the retained browse-payload helper
        # always stamps resources_subtab == "browse".
        for sub in ("", "manifest", "bogus"):
            ctx = {"webapps_root": self.root, "mode": "global", "extension_subtab": sub}
            self.assertEqual(rx._resources_browse_payload(ctx)["resources_subtab"], "browse")

    def test_create_subtab_routes_to_library_payload(self) -> None:
        # The Create subtab uses the two-pane LIBRARY payload (upload form +
        # retitle/rename/delete) — the only path carrying upload_action.
        p = rx._resources_library_payload(self.root)
        self.assertEqual(p["resources_mode"], "library")
        self.assertEqual(p["upload_action"]["route"], "/portal/api/resources/upload")

    def test_browse_hierarchy_includes_unregistered_on_disk_types(self) -> None:
        # The cluster map must include EVERY on-disk leaflet type — not just the
        # manifest-registered ones — so icons/images/docs/audio are all browsable.
        audio = self.root / "clients" / "_shared" / "site-core" / "audio"
        audio.mkdir(parents=True, exist_ok=True)
        (audio / "0000-00-00.artifact-audio.fnd.welcome.yaml").write_text("x\n", encoding="utf-8")
        slugs = {n["full_slug"] for n in self._browse(browse_view="hierarchy")["nodes"]}
        self.assertIn("artifact-audio", slugs)
        self.assertIn("artifact-icon", slugs)


class FieldIconConvention(unittest.TestCase):
    """The field/value → icon convention (content representation; SEPARATE from the
    type→icon manifest)."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        _seed(self.root)

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_resolve_field_links_contacts_and_socials(self) -> None:
        profile = {
            "website": "example.org",
            "email": "a@b.org",
            "phone": "(234) 334-4622",
            "socials": [
                {"platform": "instagram", "value": "https://instagram.com/x"},
                {"platform": "x", "value": "https://x.com/y"},
                {"platform": "weirdnet", "value": "https://weird.net/z"},
            ],
        }
        by_kind = {link["kind"]: link for link in rx.resolve_field_links(profile, self.root)}
        self.assertEqual(by_kind["website"]["icon_ref"], "0000-00-00.artifact-icon.mycite.globe")
        self.assertEqual(by_kind["website"]["href"], "https://example.org")
        self.assertEqual(by_kind["email"]["href"], "mailto:a@b.org")
        self.assertTrue(by_kind["phone"]["href"].startswith("tel:"))
        self.assertEqual(by_kind["instagram"]["icon_ref"], "0000-00-00.artifact-logo.instagram.logo")
        self.assertEqual(by_kind["x"]["icon_ref"], "0000-00-00.artifact-logo.x_twitter.logo")
        # unknown social platform still renders, with the generic 'link' icon
        self.assertEqual(by_kind["weirdnet"]["icon_ref"], "0000-00-00.artifact-icon.mycite-ui.link")
        self.assertTrue(by_kind["website"]["icon_url"].endswith(".svg"))

    def test_resolve_profile_scopes(self) -> None:
        # Grantee-scoped extra fields surface as one block per scope, with contact/
        # social values inside the block resolved to field-icon links.
        profile = {"scope_fields": {"cvcc": {"lease_id": "CI-07", "website": "tillff.square.site"}}}
        scopes = rx.resolve_profile_scopes(profile, self.root)
        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0]["scope"], "cvcc")
        self.assertEqual(scopes[0]["label"], "CVCC")
        self.assertIn("lease_id", {f["key"] for f in scopes[0]["fields"]})
        self.assertIn("website", {link["kind"] for link in scopes[0]["links"]})
        self.assertEqual(rx.resolve_profile_scopes({}, self.root), [])

    def test_field_icon_override_roundtrip(self) -> None:
        self.assertEqual(
            rx.load_field_icon_map(self.root)["website"], "0000-00-00.artifact-icon.mycite.globe"
        )
        res = rx.set_field_icon(self.root, "website", "0000-00-00.artifact-icon.mycite.webpage")
        self.assertTrue(res["ok"], res)
        self.assertEqual(
            rx.load_field_icon_map(self.root)["website"], "0000-00-00.artifact-icon.mycite.webpage"
        )
        rx.set_field_icon(self.root, "website", "")  # reset → seeded default
        self.assertEqual(
            rx.load_field_icon_map(self.root)["website"], "0000-00-00.artifact-icon.mycite.globe"
        )


if __name__ == "__main__":
    unittest.main()
