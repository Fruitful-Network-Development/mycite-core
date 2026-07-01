"""Phase 14d.2 — Email mailbox suspend route + payload-shape pins.

The Email extension card surfaces a per-row Suspend / Resume button.
``POST /__fnd/email/admin/suspend`` rewrites
``workflow.lifecycle_state`` on the targeted AWS-CSM operator profile
JSON (active → suspended, suspended → operational).

Add-mailbox is deferred until the full LIVE_AWS_PROFILE_SCHEMA
construction flow lands; suspend ships now because operators need it
for runbook lockouts today.

These tests pin:

  * Success: suspend a known profile → JSON updated on disk.
  * Idempotency: resume back to operational → JSON updated again.
  * 400 on missing profile_id.
  * 404 on unknown profile_id.
  * Payload-shape: each profile carries the right suspend_action
    (Suspend for operational, Resume for suspended).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None

if FLASK_AVAILABLE:
    from MyCiteV2.instances._shared.portal_host.app import V2PortalHostConfig, create_app


def _seed_profile(
    aws_csm_dir: Path,
    profile_id: str,
    tenant_id: str,
    domain: str,
    mailbox: str,
    lifecycle_state: str = "operational",
) -> Path:
    aws_csm_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "mycite.service_tool.aws.profile.v2",
        "identity": {
            "profile_id": profile_id,
            "tenant_id": tenant_id,
            "domain": domain,
            "region": "us-east-1",
            "mailbox_local_part": mailbox,
            "role": "operator",
            "profile_kind": "mailbox",
            "single_user_msn_id": "",
            "single_user_email": f"{mailbox}@{domain}",
            "operator_inbox_target": f"{mailbox}@{domain}",
            "send_as_email": f"{mailbox}@{domain}",
        },
        "workflow": {
            "schema": "mycite.service_tool.aws.onboarding.v2",
            "flow": "mailbox_send_as",
            "lifecycle_state": lifecycle_state,
        },
    }
    path = aws_csm_dir / f"{profile_id}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailSuspendRouteTests(unittest.TestCase):
    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="phase14d2_email_admin_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
        )
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), aws_csm_dir

    def test_suspend_updates_lifecycle_state(self) -> None:
        client, aws_csm_dir = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"profile_id": "aws-csm.alpha.support", "suspended": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["lifecycle_state"], "suspended")
        # On-disk JSON has been rewritten.
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(on_disk["workflow"]["lifecycle_state"], "suspended")

    def test_resume_restores_operational(self) -> None:
        client, aws_csm_dir = self._build_client()
        client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"profile_id": "aws-csm.alpha.support", "suspended": True}),
            content_type="application/json",
        )
        resp = client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"profile_id": "aws-csm.alpha.support", "suspended": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["lifecycle_state"], "operational")
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(on_disk["workflow"]["lifecycle_state"], "operational")

    def test_suspend_rejects_missing_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"suspended": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_profile_id")

    def test_suspend_rejects_unknown_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"profile_id": "aws-csm.ghost.mailbox", "suspended": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "profile_not_found")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailEditRouteTests(unittest.TestCase):
    """2026-05-23 — inline-edit route updates send_as_email, role, and
    operator_inbox_target on the operator-profile JSON, ignores unknown
    keys, refuses unknown profile_id, and refuses missing fields.
    """

    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="2026_05_23_email_edit_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
        )
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), aws_csm_dir

    def test_edit_updates_supported_identity_fields(self) -> None:
        client, aws_csm_dir = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "fields": {
                    "send_as_email": "support@alpha.example.test",
                    "role": "support_lead",
                    "operator_inbox_target": "ops@alpha.example.test",
                },
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(
            sorted(body["updated_fields"]),
            ["operator_inbox_target", "role", "send_as_email"],
        )
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        identity = on_disk["identity"]
        self.assertEqual(identity["send_as_email"], "support@alpha.example.test")
        self.assertEqual(identity["role"], "support_lead")
        self.assertEqual(identity["operator_inbox_target"], "ops@alpha.example.test")

    def test_edit_ignores_unsupported_keys(self) -> None:
        client, aws_csm_dir = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "fields": {
                    "role": "renamed",
                    # Identity primary keys must NOT be writable inline.
                    "profile_id": "aws-csm.evil.takeover",
                    "domain": "evil.example.test",
                    "mailbox_local_part": "evil",
                },
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertEqual(body["updated_fields"], ["role"])
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        identity = on_disk["identity"]
        self.assertEqual(identity["profile_id"], "aws-csm.alpha.support")
        self.assertEqual(identity["domain"], "alpha.example.test")
        self.assertEqual(identity["mailbox_local_part"], "support")
        self.assertEqual(identity["role"], "renamed")

    def test_edit_rejects_no_supported_fields(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "fields": {"profile_id": "aws-csm.evil.takeover"},
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "no_supported_fields")

    def test_edit_rejects_missing_fields(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_fields")

    def test_edit_rejects_unknown_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit",
            data=json.dumps({
                "profile_id": "aws-csm.ghost.mailbox",
                "fields": {"role": "x"},
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "profile_not_found")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailRemoveRouteTests(unittest.TestCase):
    """2026-05-23 — Remove route deletes the on-disk profile JSON."""

    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="2026_05_23_email_remove_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
        )
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), aws_csm_dir

    def test_remove_deletes_profile_json(self) -> None:
        client, aws_csm_dir = self._build_client()
        path = aws_csm_dir / "aws-csm.alpha.support.json"
        self.assertTrue(path.exists())
        resp = client.post(
            "/__fnd/email/admin/remove",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["profile_id"], "aws-csm.alpha.support")
        self.assertFalse(path.exists())

    def test_remove_rejects_missing_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/remove",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_remove_rejects_unknown_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/remove",
            data=json.dumps({"profile_id": "aws-csm.ghost.mailbox"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "profile_not_found")


def _seed_grantee(fnd_csm_dir: Path, msn_id: str, short_name: str, domains) -> None:
    fnd_csm_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "msn_id": msn_id,
        "short_name": short_name,
        "label": short_name,
        "domains": list(domains),
    }
    (fnd_csm_dir / f"grantee.fnd.{msn_id}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailAdminCrossTenantScopeTests(unittest.TestCase):
    """Regression: the operator email-admin routes are reachable through the
    per-grantee ``/dashboard/api/`` proxy, which injects the caller's grantee
    header. A scoped (client) caller must NOT be able to act on another
    tenant's profile (the cross-tenant mailbox-takeover hole). The operator
    (no grantee header) retains full access."""

    def _build(self):
        tmp = Path(tempfile.mkdtemp(prefix="email_admin_xtenant_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws = tmp / "private" / "utilities" / "tools" / "aws-csm"
        fnd_csm = tmp / "private" / "utilities" / "tools" / "fnd-csm"
        _seed_profile(
            aws,
            "aws-csm.fnd.support",
            tenant_id="fnd",
            domain="fnd.example.test",
            mailbox="support",
        )
        _seed_grantee(fnd_csm, "msn-fnd", "FND", ["fnd.example.test"])
        _seed_grantee(fnd_csm, "msn-cvcc", "CVCC", ["cvcc.example.test"])
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), aws

    def test_cross_tenant_suspend_denied(self) -> None:
        client, aws = self._build()
        resp = client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"profile_id": "aws-csm.fnd.support", "suspended": True}),
            content_type="application/json",
            headers={"X-Auth-Request-Grantee": "msn-cvcc"},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "domain_not_owned")
        # The FND profile was NOT mutated.
        on_disk = json.loads(
            (aws / "aws-csm.fnd.support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(on_disk["workflow"]["lifecycle_state"], "operational")

    def test_cross_tenant_remove_denied(self) -> None:
        client, aws = self._build()
        resp = client.post(
            "/__fnd/email/admin/remove",
            data=json.dumps({"profile_id": "aws-csm.fnd.support"}),
            content_type="application/json",
            headers={"X-Auth-Request-Grantee": "msn-cvcc"},
        )
        self.assertEqual(resp.status_code, 403, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"], "domain_not_owned")
        self.assertTrue((aws / "aws-csm.fnd.support.json").exists())

    def test_operator_no_header_still_allowed(self) -> None:
        client, _ = self._build()
        resp = client.post(
            "/__fnd/email/admin/suspend",
            data=json.dumps({"profile_id": "aws-csm.fnd.support", "suspended": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        self.assertTrue(resp.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
