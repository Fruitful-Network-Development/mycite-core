from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import _bootstrap_request
from MyCiteV2.packages.state_machine.portal_shell import SYSTEM_ROOT_SURFACE_ID

_AGRO_DOC = "lv.3-2-3.agro_erp.farm_profile." + ("a" * 64)


class SystemRootBootstrapSurfaceQueryTests(unittest.TestCase):
    """Stage 3a: /portal/system is reducer-owned but delegates to the unified
    workbench. The bootstrap must carry the workbench surface_query (document,
    mode, row, sandbox_filter) or a deep-linked/bookmarked document is dropped
    on initial load and the view falls back to the system sandbox."""

    def test_deep_linked_document_is_attached_as_surface_query(self) -> None:
        payload = _bootstrap_request(
            SYSTEM_ROOT_SURFACE_ID,
            portal_instance_id="fnd",
            query_params={"document": _AGRO_DOC, "mode": "datums", "row": "4-2-2"},
        )
        # shell_state is still built (reducer-owned), AND surface_query is added.
        self.assertIn("shell_state", payload)
        surface_query = payload.get("surface_query")
        self.assertIsNotNone(surface_query)
        self.assertEqual(surface_query["document"], _AGRO_DOC)
        self.assertEqual(surface_query["mode"], "datums")
        self.assertEqual(surface_query["row"], "4-2-2")
        # Sandbox inferred from the canonical id so the doc opens in agro_erp.
        self.assertEqual(surface_query["sandbox_filter"], "agro_erp")

    def test_legacy_sandbox_alias_is_canonicalized(self) -> None:
        payload = _bootstrap_request(
            SYSTEM_ROOT_SURFACE_ID,
            portal_instance_id="fnd",
            query_params={"sandbox": "agro_erp"},
        )
        self.assertEqual(payload["surface_query"]["sandbox_filter"], "agro_erp")

    def test_no_query_leaves_surface_query_absent(self) -> None:
        payload = _bootstrap_request(
            SYSTEM_ROOT_SURFACE_ID, portal_instance_id="fnd", query_params={}
        )
        self.assertNotIn("surface_query", payload)


if __name__ == "__main__":
    unittest.main()
