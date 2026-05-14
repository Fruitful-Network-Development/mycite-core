"""Portal host integration smoke for the one-shell architecture.

Pre-Phase-7 this file pinned the aws-csm + fnd-dcm + paypal-csm action
routes + a heavyweight canonical-routes assertion that enumerated the
asset manifest module list. Phase 7 (`Phase 7 — Remove legacy tool
infrastructure (AWS-CSM, FND-DCM, FND-EBI, PayPal-CSM)`) deleted those
routes and modules; Phases 0-6 of TASK-PORTAL-SIMPLIFICATION further
retired the FND-CSM tool surface and the interface_panel renderers.
The legacy assertions in this file have been stale since then. Per
the Phase 12 triage they are deleted here rather than rewritten —
asset-manifest module presence is now pinned by
`tests/architecture/test_asset_manifest_module_presence.py` (Phase 12e)
and canonical-route coverage by the per-route tests next to each
surface.

What survives is the small DOM/posture pin below, which checks the
boot script + shell core for the routing/composition markers the
client hydration depends on. That assertion never touched a retired
route and is the only thing in this file with no overlap to other
architecture tests.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class PortalHostOneShellIntegrationTests(unittest.TestCase):
    def test_client_boot_prefers_server_shell_posture_on_first_v2_hydration(self) -> None:
        portal_js = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "portal.js"
        ).read_text(encoding="utf-8")
        shell_core = (
            REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_shell_core.js"
        ).read_text(encoding="utf-8")

        self.assertIn("firstV2ShellCompositionApplied", portal_js)
        self.assertIn("applyShellPostureFromDom({ useStoredWorkbenchPreference: false })", portal_js)
        self.assertIn("syncFromDom: (options) => layoutApi.syncFromDom && layoutApi.syncFromDom(options)", portal_js)
        self.assertIn("routeKeyFromUrl", shell_core)
        self.assertIn("fromShellComposition: true", shell_core)
        self.assertIn("routeKey: routeKey", shell_core)


if __name__ == "__main__":
    unittest.main()
