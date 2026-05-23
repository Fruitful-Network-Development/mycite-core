"""C3 — /__fnd/email/admin/dmarc-ramp route.

Pins:
  * Advisory by default (no confirm) — returns decision, applies nothing.
  * confirm=true but blocked (no alignment/dwell) — applies nothing.
  * confirm=true AND all preconditions met — calls apply_dmarc_policy.
  * missing domain → 400.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _config():
    tmp = Path(tempfile.mkdtemp(prefix="c3_dmarc_"))
    for sub in ("public", "private", "data", "webapps"):
        (tmp / sub).mkdir()
    return V2PortalHostConfig(
        portal_instance_id="fnd",
        public_dir=tmp / "public",
        private_dir=tmp / "private",
        data_dir=tmp / "data",
        portal_domain="example.test",
        webapps_root=tmp / "webapps",
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class DmarcRampRouteTests(unittest.TestCase):
    def _peripheral_at_p_none(self, *, mail_from_status="Success"):
        """A stub _aws_peripheral whose domain is at p=none with MAIL FROM
        Success, so the only gating factors are alignment + dwell."""
        from unittest.mock import MagicMock
        peripheral = MagicMock()
        peripheral.get_dmarc_policy.return_value = {
            "ok": True,
            "domain": "example.test",
            "zone_id": "Z1",
            "record": "v=DMARC1; p=none; rua=mailto:r@x.com; adkim=s; aspf=s",
            "tags": {"v": "DMARC1", "p": "none", "pct": "100", "rua": "mailto:r@x.com"},
        }
        ses_client = MagicMock()
        ses_client.get_identity_mail_from_domain_attributes.return_value = {
            "MailFromDomainAttributes": {
                "example.test": {"MailFromDomainStatus": mail_from_status}
            }
        }
        peripheral._client.return_value = ses_client
        peripheral.apply_dmarc_policy.return_value = {
            "ok": True, "dry_run": False, "domain": "example.test",
            "applied_record": '"v=DMARC1; p=quarantine; pct=20; ..."',
        }
        return peripheral

    def test_missing_domain_400(self) -> None:
        with patch("MyCiteV2.instances._shared.portal_host.app._aws_peripheral",
                   self._peripheral_at_p_none()):
            client = create_app(_config()).test_client()
            resp = client.post(
                "/__fnd/email/admin/dmarc-ramp",
                data=json.dumps({}), content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)

    def test_advisory_by_default_applies_nothing(self) -> None:
        peripheral = self._peripheral_at_p_none()
        with patch("MyCiteV2.instances._shared.portal_host.app._aws_peripheral", peripheral):
            client = create_app(_config()).test_client()
            resp = client.post(
                "/__fnd/email/admin/dmarc-ramp",
                data=json.dumps({
                    "domain": "example.test",
                    "alignment_pct": 99, "days_at_current": 14,
                    # no confirm
                }),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertFalse(body["applied"])
        self.assertEqual(body["decision"]["proposed_policy"], "quarantine")
        peripheral.apply_dmarc_policy.assert_not_called()

    def test_confirm_but_blocked_applies_nothing(self) -> None:
        peripheral = self._peripheral_at_p_none()
        with patch("MyCiteV2.instances._shared.portal_host.app._aws_peripheral", peripheral):
            client = create_app(_config()).test_client()
            resp = client.post(
                "/__fnd/email/admin/dmarc-ramp",
                data=json.dumps({
                    "domain": "example.test",
                    "confirm": True,
                    # no alignment / dwell → blocked
                }),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertFalse(body["applied"])
        self.assertTrue(body["decision"]["blockers"])
        peripheral.apply_dmarc_policy.assert_not_called()

    def test_confirm_and_allowed_applies(self) -> None:
        peripheral = self._peripheral_at_p_none()
        with patch("MyCiteV2.instances._shared.portal_host.app._aws_peripheral", peripheral):
            client = create_app(_config()).test_client()
            resp = client.post(
                "/__fnd/email/admin/dmarc-ramp",
                data=json.dumps({
                    "domain": "example.test",
                    "confirm": True,
                    "alignment_pct": 99, "days_at_current": 14,
                }),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["applied"])
        peripheral.apply_dmarc_policy.assert_called_once()

    def test_mail_from_not_live_blocks_even_with_confirm(self) -> None:
        peripheral = self._peripheral_at_p_none(mail_from_status="Pending")
        with patch("MyCiteV2.instances._shared.portal_host.app._aws_peripheral", peripheral):
            client = create_app(_config()).test_client()
            resp = client.post(
                "/__fnd/email/admin/dmarc-ramp",
                data=json.dumps({
                    "domain": "example.test",
                    "confirm": True,
                    "alignment_pct": 99, "days_at_current": 14,
                }),
                content_type="application/json",
            )
        body = resp.get_json()
        self.assertFalse(body["applied"])
        self.assertFalse(body["mail_from_live"])
        peripheral.apply_dmarc_policy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
