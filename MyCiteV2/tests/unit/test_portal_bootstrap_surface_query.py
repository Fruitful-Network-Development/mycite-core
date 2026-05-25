from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.portal_host.app import _bootstrap_request
from MyCiteV2.packages.state_machine.portal_shell import (
    SYSTEM_ROOT_SURFACE_ID,
    canonical_query_for_surface_query,
)

_AGRO_DOC = "lv.3-2-3.agro_erp.farm_profile." + ("a" * 64)


class SystemRootBootstrapSurfaceQueryTests(unittest.TestCase):
    """Phase A: /portal/system is query-native — the bootstrap carries the
    workbench query as surface_query (NOT a reducer shell_state), and server
    canonicalization (sandbox alias + sandbox inference) resolves it. A
    deep-linked/bookmarked document must survive initial load instead of
    falling back to the system sandbox."""

    def test_bootstrap_is_query_native_not_reducer_owned(self) -> None:
        payload = _bootstrap_request(
            SYSTEM_ROOT_SURFACE_ID,
            portal_instance_id="fnd",
            query_params={"document": _AGRO_DOC, "mode": "datums", "row": "4-2-2"},
        )
        # No reducer shell_state for system.root anymore; the workbench query
        # travels as surface_query.
        self.assertNotIn("shell_state", payload)
        surface_query = payload["surface_query"]
        self.assertEqual(surface_query["document"], _AGRO_DOC)
        self.assertEqual(surface_query["mode"], "datums")
        self.assertEqual(surface_query["row"], "4-2-2")

    def test_no_query_leaves_surface_query_absent(self) -> None:
        payload = _bootstrap_request(
            SYSTEM_ROOT_SURFACE_ID, portal_instance_id="fnd", query_params={}
        )
        self.assertNotIn("surface_query", payload)
        self.assertNotIn("shell_state", payload)

    def test_server_canonicalization_resolves_sandbox_for_system_root(self) -> None:
        # The bootstrap passes params through raw; canonicalization (alias +
        # inference from the canonical document id) happens server-side via
        # the same canonicalizer the workbench uses.
        out = canonical_query_for_surface_query(
            {"document": _AGRO_DOC, "mode": "datums"}, surface_id=SYSTEM_ROOT_SURFACE_ID
        )
        self.assertEqual(out["sandbox_filter"], "agro_erp")
        out_alias = canonical_query_for_surface_query(
            {"sandbox": "agro_erp"}, surface_id=SYSTEM_ROOT_SURFACE_ID
        )
        self.assertEqual(out_alias["sandbox_filter"], "agro_erp")


if __name__ == "__main__":
    unittest.main()
