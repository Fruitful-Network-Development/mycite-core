from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_fnd_ebi_runtime import run_portal_fnd_ebi
from MyCiteV2.instances._shared.runtime.portal_shell_runtime import run_portal_shell_entry
from MyCiteV2.packages.state_machine.portal_shell import initial_portal_shell_state


class PortalFndEbiRuntimeTests(unittest.TestCase):
    def test_direct_fnd_ebi_endpoint_matches_shell_runtime_envelope(self) -> None:
        with TemporaryDirectory() as temp_dir:
            webapps_root = Path(temp_dir) / "webapps"
            webapps_root.mkdir(parents=True, exist_ok=True)
            shell_state = initial_portal_shell_state(
                surface_id="system.tools.fnd_ebi",
                portal_scope={"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
            )
            request_payload = {
                "schema": "mycite.v2.portal.system.tools.fnd_ebi.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["fnd_peripheral_routing"]},
                "shell_state": shell_state.to_dict(),
            }

            direct_envelope = run_portal_fnd_ebi(
                request_payload,
                webapps_root=webapps_root,
                private_dir=None,
                tool_exposure_policy={"configured_tools": {"fnd_ebi": True}, "enabled_tools": {"fnd_ebi": True}},
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
            )
            shell_envelope = run_portal_shell_entry(
                {
                    "schema": "mycite.v2.portal.shell.request.v1",
                    "requested_surface_id": "system.tools.fnd_ebi",
                    "portal_scope": request_payload["portal_scope"],
                    "shell_state": request_payload["shell_state"],
                },
                portal_instance_id="fnd",
                portal_domain="fruitfulnetworkdevelopment.com",
                webapps_root=webapps_root,
                private_dir=None,
                tool_exposure_policy={"configured_tools": {"fnd_ebi": True}, "enabled_tools": {"fnd_ebi": True}},
            )

            self.assertEqual(direct_envelope, shell_envelope)


if __name__ == "__main__":
    unittest.main()
