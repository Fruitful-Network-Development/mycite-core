"""Visual site editor backend: content shape, owner gallery, swap-by-path, text edits."""

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

SITE = "fruitfulnetworkdevelopment.com"          # the one EDITABLE_SITES entry
ENTITY = "fruitful_network_development_llc"        # entity_for_domain(SITE)
IMG_A = f"/assets/images/0000-00-00.artifact-image.{ENTITY}.a.avif"
IMG_B = f"/assets/images/0000-00-00.artifact-image.{ENTITY}.b.avif"
IMG_FOREIGN = "/assets/images/0000-00-00.artifact-image.someone_else.z.avif"
SPRITE = "/assets/icons/0000-00-00.artifact-icon.mycite-ui.sprite.svg"
ICON1 = SPRITE + "#icon-mail"
ICON2 = SPRITE + "#icon-arrow-right"


def _manifest():
    html = (
        '<h1 data-fnd-edit="hero:title">{{title}}</h1>'
        f'<img src="{IMG_A}">'
        f'<svg><use href="{ICON1}"/></svg>'
    )
    return {
        "schema_identifier": "x",
        "pages": {
            "index": {
                "file": "index.html", "template": "fnd_home", "title": "Home",
                "content": {"sections": [
                    {"id": "hero", "editor": {"label": "Hero"}, "html": html,
                     "fields": [{"key": "title", "label": "Headline", "type": "text",
                                 "value": "Old", "max_chars": 10}]},
                    {"id": "static", "html": "<p>fixed</p>"},
                ]},
            },
            "contact": {"file": "contact.html", "template": "fnd_contact", "title": "Contact",
                        "content": {"sections": [{"id": "c", "html": "<p>x</p>"}]}},
        },
    }


class SiteContentTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.assets = self.root / "clients" / SITE / "frontend" / "assets"
        self.assets.mkdir(parents=True)
        (self.root / "clients" / SITE / "frontend" / "scripts").mkdir(parents=True)
        self.manifest_path = self.assets / "0000-00-00.manifest.fnd.fnd.site.json"
        self.manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
        self.record = self.assets / "0000-00-00.record-manifest.x-website.shared_resources.yaml"
        self.record.write_text("resources: {}\n", encoding="utf-8")
        # Shared library: two FND-owned images + one foreign + a sprite.
        img_dir = self.root / "clients" / "_shared" / "site-core" / "image"
        img_dir.mkdir(parents=True)
        for p in (IMG_A, IMG_B, IMG_FOREIGN):
            (img_dir / p.split("/")[-1]).write_text("x", encoding="utf-8")
        icon_dir = self.root / "clients" / "_shared" / "site-core" / "icon"
        icon_dir.mkdir(parents=True)
        (icon_dir / SPRITE.split("/")[-1]).write_text(
            '<svg><symbol id="icon-mail"></symbol><symbol id="icon-arrow-right"></symbol></svg>',
            encoding="utf-8",
        )
        self._orig_render = sce._render_site
        sce._render_site = lambda frontend_dir: (True, "rebuilt")

    def tearDown(self):
        sce._render_site = self._orig_render

    def _html(self):
        m = json.loads(self.manifest_path.read_text())
        return m["pages"]["index"]["content"]["sections"][0]["html"]

    def _title(self):
        m = json.loads(self.manifest_path.read_text())
        return m["pages"]["index"]["content"]["sections"][0]["fields"][0]["value"]

    def _save(self, edits=None, swaps=None):
        return sce.save_site_content(self.root, SITE, edits or [], swaps or [])

    # ---- read ----
    def test_content_shape(self):
        d = sce.read_site_content(self.root, SITE)
        self.assertTrue(d["enabled"])
        self.assertEqual({p["page"] for p in d["pages"]}, {"index", "contact"})
        self.assertEqual(next(p["path"] for p in d["pages"] if p["page"] == "index"), "/")
        self.assertEqual(next(p["path"] for p in d["pages"] if p["page"] == "contact"), "/contact")
        self.assertEqual([s["key"] for s in d["text_slots"]], ["title"])
        # gallery = OWN images only (foreign excluded) + sprite icons
        self.assertIn(IMG_A, d["gallery"]["image"])
        self.assertIn(IMG_B, d["gallery"]["image"])
        self.assertNotIn(IMG_FOREIGN, d["gallery"]["image"])
        self.assertIn(ICON1, d["gallery"]["icon"])

    def test_non_editable_site_disabled(self):
        d = sce.read_site_content(self.root, "trappfamilyfarm.com")
        self.assertFalse(d["enabled"])
        self.assertEqual(d["pages"], [])

    # ---- text edits ----
    def test_text_within_budget(self):
        r = self._save(edits=[{"page": "index", "section_id": "hero", "key": "title", "value": "New"}])
        self.assertTrue(r["ok"])
        self.assertEqual(self._title(), "New")

    def test_text_over_budget_rejected(self):
        r = self._save(edits=[{"page": "index", "section_id": "hero", "key": "title", "value": "way too long"}])
        self.assertFalse(r["ok"])
        self.assertEqual(self._title(), "Old")  # untouched

    def test_control_chars_stripped(self):
        r = self._save(edits=[{"page": "index", "section_id": "hero", "key": "title", "value": "a\x00b\x07c"}])
        self.assertTrue(r["ok"])
        self.assertEqual(self._title(), "abc")

    # ---- image swap by path ----
    def test_image_swap_replaces_path_and_allocates(self):
        r = self._save(swaps=[{"page": "index", "old": IMG_A, "new": IMG_B}])
        self.assertTrue(r["ok"])
        self.assertIn(IMG_B, self._html())
        self.assertNotIn(IMG_A, self._html())
        self.assertIn(IMG_B, self.record.read_text())  # auto-allocated to record-manifest

    def test_swap_to_foreign_asset_rejected(self):
        r = self._save(swaps=[{"page": "index", "old": IMG_A, "new": IMG_FOREIGN}])
        self.assertFalse(r["ok"])
        self.assertIn(IMG_A, self._html())  # untouched

    def test_swap_absent_path_errors(self):
        r = self._save(swaps=[{"page": "index", "old": "/assets/images/nope.avif", "new": IMG_B}])
        self.assertFalse(r["ok"])

    def test_icon_swap(self):
        r = self._save(swaps=[{"page": "index", "old": ICON1, "new": ICON2}])
        self.assertTrue(r["ok"])
        self.assertIn(ICON2, self._html())

    def test_save_gated_off_for_non_editable_site(self):
        r = sce.save_site_content(self.root, "trappfamilyfarm.com",
                                  [{"page": "index", "section_id": "hero", "key": "title", "value": "x"}], [])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "not_editable")


if __name__ == "__main__":
    unittest.main()
