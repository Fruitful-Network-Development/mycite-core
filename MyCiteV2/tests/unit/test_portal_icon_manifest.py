"""Guards the portal icon-leaflet registry: the MC_ICONS map parses and every
iconImg("name") call site across portal static/templates references a mapped icon.
(The on-disk leaflet check lives in scripts/portal_icon_manifest.py check; the shared
icon tree is absent in CI, so this test asserts the map<->call-site contract only.)"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_SCRIPT = REPO_ROOT / "MyCiteV2/scripts/portal_icon_manifest.py"
_spec = importlib.util.spec_from_file_location("portal_icon_manifest", _SCRIPT)
assert _spec and _spec.loader
icon_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(icon_manifest)


class PortalIconManifestTests(unittest.TestCase):
    def test_map_parses_with_core_icons(self) -> None:
        icons = icon_manifest.parse_map(icon_manifest.PORTAL_JS.read_text(encoding="utf-8"))
        # the icons the spec names (ui-up/down/info/exit + domain-edit/add + kebab)
        for required in ("up", "down", "info", "exit", "edit", "add", "kebab"):
            self.assertIn(required, icons, f"MC_ICONS missing '{required}'")

    def test_every_call_site_uses_a_mapped_icon(self) -> None:
        icons = icon_manifest.parse_map(icon_manifest.PORTAL_JS.read_text(encoding="utf-8"))
        sites = icon_manifest.call_sites()
        unknown = {name: files for name, files in sites.items() if name not in icons}
        self.assertEqual(unknown, {}, f"iconImg() calls reference unmapped icons: {unknown}")


if __name__ == "__main__":
    unittest.main()
