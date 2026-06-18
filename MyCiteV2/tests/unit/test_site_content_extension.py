"""Unified site editor: content shape + value-replace save across site kinds."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    site_content_extension as sce,
)

MAN_SITE = "fruitfulnetworkdevelopment.com"        # manifest kind
MAN_ENT = "fruitful_network_development_llc"
STAT_SITE = "trappfamilyfarm.com"                   # static kind
STAT_ENT = "trapp_family_farm"

IMG_A = f"/assets/images/0000-00-00.artifact-image.{MAN_ENT}.a.avif"
IMG_B = f"/assets/images/0000-00-00.artifact-image.{MAN_ENT}.b.avif"
IMG_FOREIGN = "/assets/images/0000-00-00.artifact-image.someone_else.z.avif"
TIMG_A = f"/assets/images/0000-00-00.artifact-image.{STAT_ENT}.a.avif"
TIMG_B = f"/assets/images/0000-00-00.artifact-image.{STAT_ENT}.b.avif"


def _build_tree():
    root = Path(tempfile.mkdtemp())
    # ---- manifest site ----
    man = root / "clients" / MAN_SITE / "frontend"
    (man / "assets").mkdir(parents=True)
    (man / "scripts" / "render_lib").mkdir(parents=True)
    (man / "scripts" / "render_lib" / "site_builder.py").write_text("def build_site(p): pass\n")
    manifest = {
        "pages": {"index": {"file": "index.html", "title": "Home", "content": {
            "sections": [{"id": "hero",
                          "html": f"<h1>Welcome</h1><p>Plans &amp; pricing &mdash; clear.</p>"
                                  f"<img src=\"{IMG_A}\">"}],
            "hero_image": {"src": IMG_A},          # typed-field image (deep-walk must catch it)
        }}},
    }
    mp = man / "assets" / "0000-00-00.manifest.fnd.fnd.site.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    (man / "assets" / "0000-00-00.record-manifest.x-website.shared_resources.yaml").write_text(
        "resources: {}\n", encoding="utf-8")
    # ---- static site ----
    stat = root / "clients" / STAT_SITE / "frontend"
    stat.mkdir(parents=True)
    (stat / "index.html").write_text(f"<h1>Trapp</h1><img src=\"{TIMG_A}\">", encoding="utf-8")
    (stat / "crops.html").write_text("<h1>Crops</h1>", encoding="utf-8")
    (stat / "assets").mkdir()
    (stat / "assets" / "0000-00-00.record-manifest.x-website.shared_resources.yaml").write_text(
        "resources: {}\n", encoding="utf-8")
    # ---- shared library ----
    img_dir = root / "clients" / "_shared" / "site-core" / "image"
    img_dir.mkdir(parents=True)
    for p in (IMG_A, IMG_B, IMG_FOREIGN, TIMG_A, TIMG_B):
        (img_dir / p.split("/")[-1]).write_text("x")
    icon_dir = root / "clients" / "_shared" / "site-core" / "icon"
    icon_dir.mkdir(parents=True)
    (icon_dir / "0000-00-00.artifact-icon.mycite-ui.sprite.svg").write_text(
        '<svg><symbol id="icon-mail"></symbol></svg>')
    return root, mp, stat / "index.html"


class UnifiedEditorTests(unittest.TestCase):
    def setUp(self):
        self.root, self.man_manifest, self.stat_index = _build_tree()
        self._orig = sce._render_site
        sce._render_site = lambda fd: (True, "rebuilt")

    def tearDown(self):
        sce._render_site = self._orig

    # ---- read ----
    def test_manifest_site_read(self):
        d = sce.read_site_content(self.root, MAN_SITE)
        self.assertTrue(d["enabled"])
        self.assertEqual(d["kind"], "manifest")
        self.assertEqual(d["pages"][0]["path"], "/")
        self.assertIn(IMG_B, d["gallery"]["image"])
        self.assertNotIn(IMG_FOREIGN, d["gallery"]["image"])
        self.assertTrue(any(o.endswith("#icon-mail") for o in d["gallery"]["icon_sprite"]))

    def test_static_site_read(self):
        d = sce.read_site_content(self.root, STAT_SITE)
        self.assertTrue(d["enabled"])
        self.assertEqual(d["kind"], "static")
        self.assertEqual({p["path"] for p in d["pages"]}, {"/", "/crops"})

    # ---- manifest save (deep-walk) ----
    def test_manifest_image_swap_hits_html_and_typed_field(self):
        r = sce.save_site_content(self.root, MAN_SITE, "index",
                                  swaps=[{"old": IMG_A, "new": IMG_B, "kind": "image"}])
        self.assertTrue(r["ok"])
        m = json.loads(self.man_manifest.read_text())
        self.assertEqual(m["pages"]["index"]["content"]["hero_image"]["src"], IMG_B)   # typed field
        self.assertIn(IMG_B, m["pages"]["index"]["content"]["sections"][0]["html"])    # html blob
        self.assertNotIn(IMG_A, json.dumps(m))

    def test_manifest_text_edit_unique(self):
        r = sce.save_site_content(self.root, MAN_SITE, "index",
                                  edits=[{"old": "Welcome", "new": "Hello"}])
        self.assertTrue(r["ok"])
        self.assertIn("<h1>Hello</h1>", self.man_manifest.read_text())

    def test_manifest_text_edit_entity_tolerant(self):
        # The Design tab captures rendered textContent (unicode "—" / "&"), but the
        # source stores NAMED entities (&mdash; / &amp;). The edit must still place —
        # this is the "Save failed: HTTP 400" bug (every em-dash/ampersand sentence
        # failed because matching only tried raw + html.escape, not named entities).
        r = sce.save_site_content(
            self.root, MAN_SITE, "index",
            edits=[{"old": "Plans & pricing — clear.", "new": "Plans & pricing — crystal clear."}],
        )
        self.assertTrue(r["ok"], r)
        self.assertIn("crystal clear", self.man_manifest.read_text())

    def test_manifest_foreign_swap_rejected(self):
        r = sce.save_site_content(self.root, MAN_SITE, "index",
                                  swaps=[{"old": IMG_A, "new": IMG_FOREIGN, "kind": "image"}])
        self.assertFalse(r["ok"])
        self.assertIn(IMG_A, self.man_manifest.read_text())

    def test_manifest_edit_scoped_to_page_no_bleed(self):
        # The same heading appears on two pages; editing it on `index` must NOT
        # mutate the identical text on `about` (cross-page bleed).
        m = json.loads(self.man_manifest.read_text())
        m["pages"]["index"]["content"]["sections"][0]["html"] += "<h2>Our Mission</h2>"
        m["pages"]["about"] = {"file": "about.html", "title": "About",
                               "content": {"sections": [{"id": "a", "html": "<h2>Our Mission</h2>"}]}}
        self.man_manifest.write_text(json.dumps(m), encoding="utf-8")
        r = sce.save_site_content(self.root, MAN_SITE, "index",
                                  edits=[{"old": "Our Mission", "new": "Our Purpose"}])
        self.assertTrue(r["ok"], r)
        out = json.loads(self.man_manifest.read_text())
        self.assertIn("Our Purpose", out["pages"]["index"]["content"]["sections"][0]["html"])
        self.assertEqual("<h2>Our Mission</h2>",
                         out["pages"]["about"]["content"]["sections"][0]["html"])

    def test_manifest_render_failure_rolls_back(self):
        # A render failure must roll the manifest back so the live source never
        # diverges from the (unchanged) rendered HTML.
        sce._render_site = lambda fd: (False, "render boom")
        before = self.man_manifest.read_text()
        r = sce.save_site_content(self.root, MAN_SITE, "index",
                                  edits=[{"old": "Welcome", "new": "Hello"}])
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("error"), "render_failed")
        self.assertEqual(before, self.man_manifest.read_text())

    # ---- static save (.html) ----
    def test_static_image_swap_in_html(self):
        r = sce.save_site_content(self.root, STAT_SITE, "index.html",
                                  swaps=[{"old": TIMG_A, "new": TIMG_B, "kind": "image"}])
        self.assertTrue(r["ok"])
        self.assertIn(TIMG_B, self.stat_index.read_text())
        self.assertNotIn(TIMG_A, self.stat_index.read_text())

    def test_static_text_edit(self):
        r = sce.save_site_content(self.root, STAT_SITE, "index.html",
                                  edits=[{"old": "Trapp", "new": "Trapp Farm"}])
        self.assertTrue(r["ok"])
        self.assertIn("<h1>Trapp Farm</h1>", self.stat_index.read_text())

    def test_static_save_preserves_file_mode(self):
        # Regression: the atomic writer used mkstemp (0600) + os.replace, so every
        # saved page inherited 0600 and became unreadable to nginx — the live site
        # 403'd right after a Design-tab save. A save must preserve the page's
        # existing permissions (here 0664 stays group/other readable).
        import os
        import stat
        os.chmod(self.stat_index, 0o664)
        r = sce.save_site_content(self.root, STAT_SITE, "index.html",
                                  edits=[{"old": "Trapp", "new": "Trapp Farm"}])
        self.assertTrue(r["ok"], r)
        mode = stat.S_IMODE(os.stat(self.stat_index).st_mode)
        self.assertTrue(mode & 0o044, f"page not group/other readable after save: {oct(mode)}")
        self.assertEqual(mode, 0o664, oct(mode))

    def test_empty_text_edit_rejected(self):
        # An inline edit must not blank content to "" / whitespace (silent loss).
        r = sce.save_site_content(self.root, STAT_SITE, "index.html",
                                  edits=[{"old": "Trapp", "new": "   "}])
        self.assertFalse(r["ok"])
        self.assertIn("<h1>Trapp</h1>", self.stat_index.read_text())

    def test_static_ambiguous_text_rejected(self):
        # "Crops" appears once on crops.html but the edit targets index.html where it's absent.
        r = sce.save_site_content(self.root, STAT_SITE, "index.html",
                                  edits=[{"old": "Nonexistent", "new": "X"}])
        self.assertFalse(r["ok"])

    def test_non_editable_site(self):
        self.assertFalse(sce.read_site_content(self.root, "example.com")["enabled"])
        r = sce.save_site_content(self.root, "example.com", "index", swaps=[{"old": "a", "new": "b"}])
        self.assertEqual(r["error"], "not_editable")


if __name__ == "__main__":
    unittest.main()
