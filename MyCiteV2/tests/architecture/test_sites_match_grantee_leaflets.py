"""SSOT guard: every render_dashboard_sites SITES entry maps to a grantee leaflet.

After the leaflet cutover the grantee identity leaflets are the single source of
truth; this test fails if the hand-maintained SITES catalog drifts from them
(a missing leaflet, or a SITES domain the leaflet does not own). Skips on hosts
without the leaflet tree (CI), so it guards drift on the live box + dev trees.
"""
from __future__ import annotations

import glob
import unittest
from pathlib import Path

import yaml

LEAFLET_DIR = Path("/srv/webapps/clients/_shared/site-core/grantee")


class SitesMatchLeafletsTest(unittest.TestCase):
    def test_each_site_has_matching_leaflet(self) -> None:
        paths = sorted(glob.glob(str(LEAFLET_DIR / "*.grantee_profile.yaml")))
        if not paths:
            self.skipTest("no grantee leaflets on this host")
        leaflets: dict[str, set[str]] = {}
        for path in paths:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
            short = str(data.get("short_name", "")).upper()
            if short:
                leaflets[short] = {str(d).lower() for d in (data.get("domains") or [])}

        from MyCiteV2.scripts.render_dashboard_sites import SITES

        for site in SITES:
            short = site.short_name.upper()
            self.assertIn(short, leaflets, f"SITES has {short} with no grantee leaflet")
            self.assertIn(
                site.domain.lower(),
                leaflets[short],
                f"{short} leaflet domains {leaflets[short]} do not include SITES domain {site.domain}",
            )


if __name__ == "__main__":
    unittest.main()
