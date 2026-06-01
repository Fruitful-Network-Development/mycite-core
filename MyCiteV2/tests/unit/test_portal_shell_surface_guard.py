"""Per-surface render guard: one surface's render failure must NOT blank the shell.

Before this guard, an exception from _bundle_for_surface propagated out of
run_portal_shell_entry → the /portal/api/v2/shell handler returned HTTP 500 → the
JS shell showFatal'd and blanked the WHOLE portal. The guard degrades to a
chrome-intact fallback whose envelope error stays None (so _runtime_status_code
returns 200, the only status the JS renders in-pane) and carries the failure inside
the workbench region's surface_payload.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import MyCiteV2.instances._shared.runtime.portal_shell_runtime as psr
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry


class SurfaceRenderGuardTests(unittest.TestCase):
    def _entry(self):
        # utilities.root is an allowed, non-SYSTEM surface, so the SQL-error branch
        # is not taken and the envelope error stays driven solely by the guard.
        with patch.object(psr, "_bundle_for_surface", side_effect=RuntimeError("boom")):
            return run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "utilities.root",
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )

    def test_render_failure_does_not_raise(self) -> None:
        envelope = self._entry()  # must not raise
        self.assertIsInstance(envelope, dict)

    def test_envelope_error_is_none_so_status_stays_200(self) -> None:
        # _runtime_status_code returns 200 only when envelope.error is falsy; a
        # populated error → 4xx/5xx → JS blanks. The guard must leave it None.
        self.assertIsNone(self._entry()["error"])

    def test_shell_composition_has_regions(self) -> None:
        # applyEnvelope showFatal's unless shell_composition.regions exists.
        composition = self._entry()["shell_composition"]
        self.assertTrue(composition.get("regions"))

    def test_failure_message_rides_in_surface_payload(self) -> None:
        # The message must be renderable content (sections), not the envelope error.
        envelope = self._entry()
        self.assertIn("could not be rendered", json.dumps(envelope))

    def test_failure_is_observable_in_warnings(self) -> None:
        warnings = self._entry().get("warnings") or []
        self.assertTrue(any(w.get("code") == "surface_render_failed" for w in warnings))

    def test_system_root_with_healthy_db_degrades_gracefully(self) -> None:
        # The actual outage shape: a code bug raises while rendering system.root
        # (the default landing surface) on a HEALTHY db. The post-except SQL-error
        # branch returns None, so the envelope error stays None → 200 → in-pane,
        # instead of the pre-fix 500 that blanked the whole portal.
        with patch.object(psr, "_bundle_for_surface", side_effect=RuntimeError("boom")), patch.object(
            psr, "_sql_runtime_error_for_surface", return_value=None
        ):
            envelope = run_portal_shell_entry(
                {"schema": "mycite.v2.portal.shell.request.v1", "requested_surface_id": "system.root"},
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
        self.assertEqual(envelope["surface_id"], "system.root")
        self.assertIsNone(envelope["error"])
        self.assertIn("could not be rendered", json.dumps(envelope))


if __name__ == "__main__":
    unittest.main()
