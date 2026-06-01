"""Tests for dashboard_aggregate (Home + Email payload builders).

Pure-function tests with stub adapters — no portal app, no real MOS,
no AWS. The point is to verify the *shape* and the *gap behavior*
(SES events not wired ⇒ deliverability.available=False).
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.utilities_extensions.dashboard_aggregate import (
    build_email_dashboard,
    build_grantee_summary,
)

GRANTEE_MSN = "9-9-9"
DOMAIN = "example.com"


class _StubDeliverabilityAdapter:
    def __init__(self, rollup):
        self._rollup = rollup

    def load_rollup(self, *, domain: str, period=None):
        return {**self._rollup, "period": {"from": period[0] if period else "",
                                            "to": period[1] if period else ""}}


class _StubAwsPeripheral:
    def __init__(self, status):
        self._status = status

    def describe_domain_status(self, *, domain: str):
        return self._status


def _write_grantee_profile(root: Path, *, msn: str = GRANTEE_MSN,
                            short: str = "EX", label: str = "Example",
                            domains: list[str] | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "mycite.v2.grantee.profile.v1",
        "msn_id": msn,
        "short_name": short,
        "label": label,
        "domains": domains or [DOMAIN],
        "users": ["test@example.com"],
        "aws_ses": {
            "from_address": "noreply@example.com",
            "configuration_set": "fnd-default",
        },
    }
    (root / f"grantee.fnd.{msn}.json").write_text(json.dumps(payload), encoding="utf-8")


class HomeSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private_dir = Path(self.tmp.name)
        self.fnd_csm_root = self.private_dir / "utilities" / "tools" / "fnd-csm"
        _write_grantee_profile(self.fnd_csm_root)
        (self.private_dir / "utilities" / "tools" / "aws-csm" / "newsletter").mkdir(parents=True)
        # Seed analytics NDJSON so total_events + unique_visitors are non-zero.
        analytics_dir = self.private_dir / "utilities" / "tools" / "analytics"
        analytics_dir.mkdir(parents=True)
        ndjson = analytics_dir / f"analytics.{DOMAIN}.events.2026-05.ndjson"
        events = [
            {"occurred_at_utc": "2026-05-10T12:00:00Z", "is_bot": False,
             "visitor_cookie_id_hash": "v1", "event_type": "page_view"},
            {"occurred_at_utc": "2026-05-11T12:00:00Z", "is_bot": False,
             "visitor_cookie_id_hash": "v2", "event_type": "page_view"},
            {"occurred_at_utc": "2026-05-12T12:00:00Z", "is_bot": True,
             "visitor_cookie_id_hash": "v3", "event_type": "page_view"},
        ]
        ndjson.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

    def test_home_summary_has_canonical_shape(self) -> None:
        payload = build_grantee_summary(
            msn_id=GRANTEE_MSN,
            period=(date(2026, 5, 1), date(2026, 5, 31)),
            fnd_csm_root=self.fnd_csm_root,
            aws_peripheral=_StubAwsPeripheral({
                "ses_identity_verified": True,
                "dkim_verified": True,
                "mx_present": True,
            }),
            private_dir=self.private_dir,
        )
        self.assertEqual(payload["grantee"]["msn_id"], GRANTEE_MSN)
        self.assertEqual(payload["grantee"]["short_name"], "EX")
        self.assertEqual(payload["grantee"]["domains"], [DOMAIN])
        self.assertEqual(payload["period"], {"from": "2026-05-01", "to": "2026-05-31"})
        for key in ("total_events", "unique_visitors", "bandwidth_gb",
                    "subscribers", "dispatches", "tolled_amount_usd"):
            self.assertIn(key, payload["quick_counts"])
        # 3 events ingested (2 human + 1 bot); 2 unique humans.
        self.assertEqual(payload["quick_counts"]["total_events"], 3)
        self.assertEqual(payload["quick_counts"]["unique_visitors"], 2)
        self.assertEqual(len(payload["identity_status"]), 1)
        status = payload["identity_status"][0]
        self.assertEqual(status["domain"], DOMAIN)
        self.assertIs(status["ses_verified"], True)
        self.assertIs(status["dkim_verified"], True)
        self.assertIs(status["mx_ok"], True)

    def test_home_summary_identity_status_when_peripheral_raises(self) -> None:
        class Broken:
            def describe_domain_status(self, *, domain):
                raise RuntimeError("AWS creds missing")

        payload = build_grantee_summary(
            msn_id=GRANTEE_MSN,
            period=(date(2026, 5, 1), date(2026, 5, 31)),
            fnd_csm_root=self.fnd_csm_root,
            aws_peripheral=Broken(),
            private_dir=self.private_dir,
        )
        status = payload["identity_status"][0]
        self.assertIsNone(status["ses_verified"])
        self.assertIsNone(status["dkim_verified"])
        self.assertIsNone(status["mx_ok"])


class EmailDashboardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.private_dir = Path(self.tmp.name)
        self.fnd_csm_root = self.private_dir / "utilities" / "tools" / "fnd-csm"
        _write_grantee_profile(self.fnd_csm_root)
        # Empty newsletter + aws-csm dirs.
        self.contacts_dir = self.private_dir / "utilities" / "tools" / "aws-csm" / "newsletter"
        self.contacts_dir.mkdir(parents=True)

    def _write_contact_log(self, contacts, dispatches=()):
        payload = {"contacts": contacts, "dispatches": list(dispatches)}
        (self.contacts_dir / f"newsletter.{DOMAIN}.contacts.json").write_text(
            json.dumps(payload), encoding="utf-8")

    def test_deliverability_available_false_when_no_ses_pipeline(self) -> None:
        # _StubDeliverabilityAdapter returns available=False shape.
        payload = build_email_dashboard(
            msn_id=GRANTEE_MSN,
            period=(date(2026, 5, 1), date(2026, 5, 31)),
            fnd_csm_root=self.fnd_csm_root,
            private_dir=self.private_dir,
            deliverability_adapter=_StubDeliverabilityAdapter({
                "available": False,
                "send_count": 0, "delivery_count": 0, "bounce_count": 0,
                "complaint_count": 0, "open_count": 0, "click_count": 0,
                "bounce_rate": 0.0, "complaint_rate": 0.0,
            }),
            aws_peripheral=_StubAwsPeripheral({
                "ses_identity_verified": True, "dkim_verified": True, "mx_present": True,
            }),
        )
        self.assertIs(payload["deliverability"]["available"], False)

    def test_deliverability_aggregates_across_domains(self) -> None:
        # Single domain ⇒ aggregation is identity, but exercises the path.
        payload = build_email_dashboard(
            msn_id=GRANTEE_MSN,
            period=(date(2026, 5, 1), date(2026, 5, 31)),
            fnd_csm_root=self.fnd_csm_root,
            private_dir=self.private_dir,
            deliverability_adapter=_StubDeliverabilityAdapter({
                "available": True,
                "send_count": 50, "delivery_count": 48, "bounce_count": 2,
                "complaint_count": 1, "open_count": 20, "click_count": 5,
                "bounce_rate": 0.04, "complaint_rate": 0.02,
            }),
            aws_peripheral=_StubAwsPeripheral({
                "ses_identity_verified": True, "dkim_verified": True, "mx_present": True,
            }),
        )
        d = payload["deliverability"]
        self.assertTrue(d["available"])
        self.assertEqual(d["send_count"], 50)
        # Rates RE-derived from totals, not propagated from the stub.
        self.assertAlmostEqual(d["bounce_rate"], 2 / 50, places=4)
        self.assertAlmostEqual(d["complaint_rate"], 1 / 50, places=4)

    def test_email_payload_includes_identity_and_contacts_and_forward_map(self) -> None:
        self._write_contact_log(
            contacts=[
                {"email": "a@x.com", "subscribed": True,
                 "subscribed_at": "2026-05-01T10:00:00Z"},
                {"email": "b@x.com", "subscribed": False,
                 "unsubscribed_at": "2026-05-15T10:00:00Z"},
            ],
            dispatches=[{
                "dispatch_id": "d-1", "completed_at": "2026-05-10T12:00:00Z",
                "subject": "Hello", "target_count": 100, "sent_count": 99,
            }],
        )
        # Forward map entry under aws-csm. Filenames follow
        # aws-csm.<short>.<user>.json; loader matches by identity.domain.
        aws_csm_dir = self.private_dir / "utilities" / "tools" / "aws-csm"
        (aws_csm_dir / "aws-csm.ex.info.json").write_text(json.dumps({
            "identity": {
                "domain": DOMAIN,
                "send_as_email": f"info@{DOMAIN}",
                "operator_inbox_target": "owner@example.com",
            },
        }), encoding="utf-8")

        payload = build_email_dashboard(
            msn_id=GRANTEE_MSN,
            period=(date(2026, 5, 1), date(2026, 5, 31)),
            fnd_csm_root=self.fnd_csm_root,
            private_dir=self.private_dir,
            deliverability_adapter=_StubDeliverabilityAdapter({"available": False}),
            aws_peripheral=_StubAwsPeripheral({
                "ses_identity_verified": True, "dkim_verified": True, "mx_present": True,
            }),
        )
        self.assertEqual(payload["identity"]["sender_address"], "noreply@example.com")
        self.assertEqual(payload["identity"]["configset"], "fnd-default")
        self.assertEqual(payload["contacts"]["subscribed_count"], 1)
        self.assertEqual(payload["contacts"]["unsubscribed_count"], 1)
        self.assertEqual(len(payload["dispatches"]), 1)
        self.assertEqual(payload["dispatches"][0]["subject"], "Hello")
        self.assertEqual(len(payload["forward_map"]), 1)
        self.assertEqual(payload["forward_map"][0]["alias"], f"info@{DOMAIN}")
        self.assertEqual(payload["forward_map"][0]["send_as_email"], "owner@example.com")


if __name__ == "__main__":
    unittest.main()
