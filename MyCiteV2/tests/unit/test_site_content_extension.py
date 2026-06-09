"""Typed-slot site-content editor: read + server-side save validation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions import (
    site_content_extension as sce,
)

SITE = "fruitfulnetworkdevelopment.com"  # the one EDITABLE_SITES entry


def _manifest():
    return {
        "schema_identifier": "x",
        "pages": {
            "index": {
                "file": "index.html",
                "template": "fnd_home",
                "content": {"sections": [
                    {"id": "hero", "editor": {"label": "Hero"}, "html": "<h1>{{title}}</h1><img src='{{pic}}'>",
                     "fields": [
                         {"key": "title", "label": "Headline", "type": "text", "value": "Old", "max_chars": 10},
                         {"key": "pic", "label": "Image", "type": "image_ref", "value": "/assets/images/a.avif"},
                     ]},
                    {"id": "static", "html": "<p>fixed</p>"},  # no fields → not editable
                ]},
            }
        },
    }


class SiteContentTests(unittest.TestCase):
    def setUp(self):
        # Fake webapps tree: clients/<SITE>/frontend/assets + a record-manifest +
        # a shared sprite under clients/_shared/site-core/icon.
        import tempfile
        self.root = Path(tempfile.mkdtemp())
        self.assets = self.root / "clients" / SITE / "frontend" / "assets"
        self.assets.mkdir(parents=True)
        (self.root / "clients" / SITE / "frontend" / "scripts").mkdir(parents=True)
        self.manifest_path = self.assets / "0000-00-00.manifest.fnd.fnd.site.json"
        self.manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
        (self.assets / "0000-00-00.record-manifest.x-website.shared_resources.yaml").write_text(
            "resources:\n"
            "  image:\n"
            "    - {asset_id: a, asset_path: /assets/images/a.avif, entity_scope: x}\n"
            "    - {asset_id: b, asset_path: /assets/images/b.avif, entity_scope: x}\n",
            encoding="utf-8",
        )
        icon_dir = self.root / "clients" / "_shared" / "site-core" / "icon"
        icon_dir.mkdir(parents=True)
        (icon_dir / "0000-00-00.artifact-icon.mycite-ui.sprite.svg").write_text(
            '<svg><symbol id="icon-mail"></symbol><symbol id="icon-arrow-right"></symbol></svg>',
            encoding="utf-8",
        )
        # Don't actually shell out to render_manifest.py in unit tests.
        self._orig_render = sce._render_site
        sce._render_site = lambda frontend_dir: (True, "rebuilt")

    def tearDown(self):
        sce._render_site = self._orig_render

    def _save(self, edits):
        return sce.save_site_content(self.root, SITE, edits)

    def _stored_title(self):
        m = json.loads(self.manifest_path.read_text())
        return m["pages"]["index"]["content"]["sections"][0]["fields"][0]["value"]

    # ---- read ----
    def test_read_lists_editable_sections_and_assets(self):
        data = sce.read_site_content(self.root, SITE)
        self.assertTrue(data["enabled"])
        self.assertEqual(len(data["sections"]), 1)  # only the section with fields
        self.assertEqual(data["sections"][0]["section_id"], "hero")
        self.assertIn("/assets/images/b.avif", data["assets"]["image"])
        self.assertTrue(any(o.endswith("#icon-mail") for o in data["assets"]["icon"]))

    def test_non_editable_site_disabled(self):
        data = sce.read_site_content(self.root, "trappfamilyfarm.com")
        self.assertFalse(data["enabled"])
        self.assertEqual(data["sections"], [])

    # ---- save: success ----
    def test_text_within_budget_applies(self):
        r = self._save([{"page": "index", "section_id": "hero", "key": "title", "value": "New name"}])
        self.assertTrue(r["ok"])
        self.assertEqual(r["applied"], 1)
        self.assertEqual(self._stored_title(), "New name")

    def test_image_swap_to_allowed_asset(self):
        r = self._save([{"page": "index", "section_id": "hero", "key": "pic", "value": "/assets/images/b.avif"}])
        self.assertTrue(r["ok"])

    # ---- save: rejection (atomic: nothing applied, manifest untouched) ----
    def test_text_over_budget_rejected(self):
        r = self._save([{"page": "index", "section_id": "hero", "key": "title", "value": "way too long a headline"}])
        self.assertFalse(r["ok"])
        self.assertTrue(any("exceeds" in e for e in r["errors"]))
        self.assertEqual(self._stored_title(), "Old")  # unchanged

    def test_image_not_in_library_rejected(self):
        r = self._save([{"page": "index", "section_id": "hero", "key": "pic", "value": "/assets/images/evil.avif"}])
        self.assertFalse(r["ok"])
        self.assertTrue(any("library" in e for e in r["errors"]))

    def test_non_editable_field_rejected(self):
        r = self._save([{"page": "index", "section_id": "static", "key": "anything", "value": "x"}])
        self.assertFalse(r["ok"])

    def test_control_chars_stripped(self):
        r = self._save([{"page": "index", "section_id": "hero", "key": "title", "value": "a\x00b\x07c"}])
        self.assertTrue(r["ok"])
        self.assertEqual(self._stored_title(), "abc")

    def test_save_gated_off_for_non_editable_site(self):
        r = sce.save_site_content(self.root, "trappfamilyfarm.com",
                                  [{"page": "index", "section_id": "hero", "key": "title", "value": "x"}])
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "not_editable")


if __name__ == "__main__":
    unittest.main()
