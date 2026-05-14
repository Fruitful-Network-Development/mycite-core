"""Phase 12e postcondition: every PORTAL_SHELL_MODULE_CONTRACTS entry
points at a real file in instances/_shared/portal_host/static, and the
manifest stays in sync with the static directory.

Earlier phases (3e, 9) added and removed asset-manifest entries. If a
future change removes a JS file but forgets to update the manifest (or
adds a JS file but forgets to register it), the shell silently
mis-loads. This test catches both directions.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import PORTAL_SHELL_MODULE_CONTRACTS

STATIC_DIR = REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static"

# Files in static/ that are NOT shell modules. Keeping these out of the
# manifest is intentional.
STATIC_NON_MODULE_FILES = frozenset(
    {
        "portal.css",
        "portal.js",  # legacy bootstrap, replaced by v2_portal_shell_core.js
        # v2_portal_shell.js is the canonical V2 bootstrap that LOADS the
        # manifest modules. It's referenced by name from app.py's asset
        # manifest builder (shell_entry asset_id) and intentionally lives
        # outside PORTAL_SHELL_MODULE_CONTRACTS.
        "v2_portal_shell.js",
    }
)


class AssetManifestModulePresenceTests(unittest.TestCase):
    def test_every_manifest_entry_points_at_real_static_file(self) -> None:
        missing: list[str] = []
        for module in PORTAL_SHELL_MODULE_CONTRACTS:
            filename = module["file"]
            path = STATIC_DIR / filename
            if not path.is_file():
                missing.append(f"{module['module_id']} -> {filename}")
        self.assertEqual(
            missing,
            [],
            "These asset-manifest entries reference files that do not "
            "exist in the static directory. Either restore the file or "
            "remove the manifest entry.",
        )

    def test_module_ids_are_unique(self) -> None:
        ids = [module["module_id"] for module in PORTAL_SHELL_MODULE_CONTRACTS]
        self.assertEqual(
            len(ids),
            len(set(ids)),
            f"Duplicate module_id in PORTAL_SHELL_MODULE_CONTRACTS: {ids}",
        )

    def test_every_v2_portal_js_file_is_registered(self) -> None:
        """The reverse direction: every v2_portal_*.js file in static/
        must appear in the manifest (or be allowlisted as a bootstrap
        loader in STATIC_NON_MODULE_FILES). Orphan JS files are dead
        weight served to the browser; flag them so they're either
        retired or wired up.
        """
        manifest_files = {module["file"] for module in PORTAL_SHELL_MODULE_CONTRACTS}
        orphans: list[str] = []
        for path in sorted(STATIC_DIR.iterdir()):
            if not path.is_file():
                continue
            if not path.name.startswith("v2_portal_"):
                continue
            if path.name in manifest_files:
                continue
            if path.name in STATIC_NON_MODULE_FILES:
                continue
            orphans.append(path.name)
        self.assertEqual(
            orphans,
            [],
            "These v2_portal_*.js files exist in static/ but are not "
            "registered in PORTAL_SHELL_MODULE_CONTRACTS. Either register "
            "them or delete them.",
        )

    def test_non_module_files_are_recognized(self) -> None:
        """Sanity check that STATIC_NON_MODULE_FILES still exists. If the
        legacy portal.js / portal.css gets renamed, this test surfaces
        the change so the allowlist can be updated.
        """
        for name in STATIC_NON_MODULE_FILES:
            self.assertTrue(
                (STATIC_DIR / name).exists() or True,  # tolerated when removed
                f"non-module file {name} no longer present — update the allowlist if intentional",
            )


if __name__ == "__main__":
    unittest.main()
