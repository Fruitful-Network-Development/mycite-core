"""C2 — profile-save post-hook refreshes the forwarder FORWARD_TO_MAP_JSON.

Pins:
  * /__fnd/email/admin/edit fires sync_operator_forwarding_routes on success.
  * /__fnd/email/admin/remove fires it on success.
  * /__fnd/email/admin/suspend does NOT (lifecycle only — routing unchanged).
  * A sync failure does NOT fail the admin action (hook is fire-and-log).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _seed_profile(aws_csm_dir: Path) -> None:
    aws_csm_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "mycite.service_tool.aws.profile.v2",
        "identity": {
            "profile_id": "aws-csm.alpha.support",
            "tenant_id": "alpha",
            "domain": "alpha.example.test",
            "mailbox_local_part": "support",
            "operator_inbox_target": "support@alpha.example.test",
            "send_as_email": "support@alpha.example.test",
            "role": "operator",
        },
        "workflow": {"lifecycle_state": "operational"},
    }
    (aws_csm_dir / "aws-csm.alpha.support.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class ForwardMapHookTests(unittest.TestCase):
    def _client_and_peripheral(self):
        tmp = Path(tempfile.mkdtemp(prefix="c2_hook_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        _seed_profile(tmp / "private" / "utilities" / "tools" / "aws-csm")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return config

    def test_edit_fires_forward_map_sync(self) -> None:
        config = self._client_and_peripheral()
        with patch(
            "MyCiteV2.instances._shared.portal_host.app._aws_peripheral"
        ) as peripheral:
            peripheral.sync_operator_forwarding_routes.return_value = {"status": "ok"}
            app = create_app(config)
            client = app.test_client()
            resp = client.post(
                "/__fnd/email/admin/edit",
                data=json.dumps({
                    "profile_id": "aws-csm.alpha.support",
                    "fields": {"send_as_email": "newaddr@alpha.example.test"},
                }),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
            peripheral.sync_operator_forwarding_routes.assert_called_once()

    def test_remove_fires_forward_map_sync(self) -> None:
        config = self._client_and_peripheral()
        with patch(
            "MyCiteV2.instances._shared.portal_host.app._aws_peripheral"
        ) as peripheral:
            peripheral.sync_operator_forwarding_routes.return_value = {"status": "ok"}
            app = create_app(config)
            client = app.test_client()
            resp = client.post(
                "/__fnd/email/admin/remove",
                data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
            peripheral.sync_operator_forwarding_routes.assert_called_once()

    def test_suspend_does_not_fire_forward_map_sync(self) -> None:
        config = self._client_and_peripheral()
        with patch(
            "MyCiteV2.instances._shared.portal_host.app._aws_peripheral"
        ) as peripheral:
            app = create_app(config)
            client = app.test_client()
            resp = client.post(
                "/__fnd/email/admin/suspend",
                data=json.dumps({"profile_id": "aws-csm.alpha.support", "suspended": True}),
                content_type="application/json",
            )
            self.assertEqual(resp.status_code, 200)
            peripheral.sync_operator_forwarding_routes.assert_not_called()

    def test_sync_failure_does_not_fail_edit(self) -> None:
        config = self._client_and_peripheral()
        with patch(
            "MyCiteV2.instances._shared.portal_host.app._aws_peripheral"
        ) as peripheral:
            peripheral.sync_operator_forwarding_routes.side_effect = RuntimeError(
                "lambda update denied"
            )
            app = create_app(config)
            client = app.test_client()
            resp = client.post(
                "/__fnd/email/admin/edit",
                data=json.dumps({
                    "profile_id": "aws-csm.alpha.support",
                    "fields": {"role": "lead"},
                }),
                content_type="application/json",
            )
            # Hook failure is swallowed; the edit itself still returns 200.
            self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
            self.assertTrue(resp.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
