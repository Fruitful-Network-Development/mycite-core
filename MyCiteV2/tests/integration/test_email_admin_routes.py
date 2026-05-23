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


class EmailExtensionPayloadSuspendActionTests(unittest.TestCase):
    """Each profile row in the email extension payload carries a
    ``suspend_action`` triple — Suspend when operational, Resume when
    suspended, empty when profile_id is missing.
    """

    def _payload_for(self, lifecycle_state: str):
        # private_dir is the root the extension consumes; profiles live
        # in the canonical ``utilities/tools/aws-csm`` subdirectory.
        tmp = Path(tempfile.mkdtemp(prefix="phase14d2_payload_"))
        aws_csm_dir = tmp / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
            lifecycle_state=lifecycle_state,
        )
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _build_email_extension_payload,
        )

        return _build_email_extension_payload(
            grantee={},
            domain="alpha.example.test",
            private_dir=tmp,
        )

    def test_operational_profile_gets_suspend_action(self) -> None:
        payload = self._payload_for("operational")
        profiles = payload.get("profiles") or []
        self.assertTrue(profiles)
        action = profiles[0].get("suspend_action") or {}
        self.assertEqual(action.get("label"), "Suspend")
        self.assertTrue(action.get("payload", {}).get("suspended"))
        self.assertEqual(action.get("route"), "/__fnd/email/admin/suspend")

    def test_suspended_profile_gets_resume_action(self) -> None:
        payload = self._payload_for("suspended")
        profiles = payload.get("profiles") or []
        self.assertTrue(profiles)
        action = profiles[0].get("suspend_action") or {}
        self.assertEqual(action.get("label"), "Resume")
        self.assertFalse(action.get("payload", {}).get("suspended"))


class EmailExtensionMultiDomainTests(unittest.TestCase):
    """Phase 16c: a grantee that owns multiple domains (e.g. CVCC owns
    both cuyahogavalleycountrysideconservancy.org + cvccboard.org)
    sees every mailbox across every domain in one flat table, each
    row tagged with its domain.
    """

    def _build_multi_domain_payload(self) -> dict:
        tmp = Path(tempfile.mkdtemp(prefix="phase16c_multi_domain_"))
        aws_csm_dir = tmp / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.cvcc.admin",
            tenant_id="cvcc",
            domain="cuyahogavalleycountrysideconservancy.org",
            mailbox="admin",
        )
        _seed_profile(
            aws_csm_dir,
            "aws-csm.cvcc.news",
            tenant_id="cvcc",
            domain="cuyahogavalleycountrysideconservancy.org",
            mailbox="news",
        )
        _seed_profile(
            aws_csm_dir,
            "aws-csm.cvccboard.daniel",
            tenant_id="cvccboard",
            domain="cvccboard.org",
            mailbox="daniel",
        )
        _seed_profile(
            aws_csm_dir,
            "aws-csm.cvccboard.elizabeth",
            tenant_id="cvccboard",
            domain="cvccboard.org",
            mailbox="elizabeth",
        )
        # An unrelated profile that must NOT leak into the CVCC list.
        _seed_profile(
            aws_csm_dir,
            "aws-csm.tff.contact",
            tenant_id="tff",
            domain="trappfamilyfarm.com",
            mailbox="contact",
        )
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _build_email_extension_payload,
        )

        return _build_email_extension_payload(
            grantee={
                "msn_id": "cvcc",
                "domains": [
                    "cuyahogavalleycountrysideconservancy.org",
                    "cvccboard.org",
                ],
            },
            domain="cuyahogavalleycountrysideconservancy.org",
            private_dir=tmp,
        )

    def test_multi_domain_grantee_shows_all_domain_profiles(self) -> None:
        payload = self._build_multi_domain_payload()
        profiles = payload.get("profiles") or []
        rows_by_id = {p["profile_id"]: p for p in profiles}
        self.assertIn("aws-csm.cvcc.admin", rows_by_id)
        self.assertIn("aws-csm.cvcc.news", rows_by_id)
        self.assertIn("aws-csm.cvccboard.daniel", rows_by_id)
        self.assertIn("aws-csm.cvccboard.elizabeth", rows_by_id)
        # Unrelated TFF profile must not leak in.
        self.assertNotIn("aws-csm.tff.contact", rows_by_id)
        # 4 CVCC mailboxes, not 2.
        self.assertEqual(len(profiles), 4)

    def test_profile_rows_carry_their_domain(self) -> None:
        payload = self._build_multi_domain_payload()
        for p in payload.get("profiles") or []:
            self.assertIn(p["domain"], {
                "cuyahogavalleycountrysideconservancy.org",
                "cvccboard.org",
            })
        # CVCC mailboxes carry the CVCC domain; cvccboard mailboxes
        # carry the cvccboard domain — no cross-pollination.
        rows_by_id = {p["profile_id"]: p for p in payload["profiles"]}
        self.assertEqual(
            rows_by_id["aws-csm.cvcc.admin"]["domain"],
            "cuyahogavalleycountrysideconservancy.org",
        )
        self.assertEqual(
            rows_by_id["aws-csm.cvccboard.daniel"]["domain"], "cvccboard.org"
        )

    def test_profile_rows_sorted_by_domain_then_mailbox(self) -> None:
        payload = self._build_multi_domain_payload()
        profiles = payload.get("profiles") or []
        keys = [(p["domain"], p["mailbox"]) for p in profiles]
        self.assertEqual(keys, sorted(keys))

    def test_grantee_domains_list_echoed_on_payload(self) -> None:
        payload = self._build_multi_domain_payload()
        self.assertEqual(
            sorted(payload.get("domains") or []),
            ["cuyahogavalleycountrysideconservancy.org", "cvccboard.org"],
        )


# ----------------------------------------------------------------------
# 2026-05-23 — correctness pass coverage
#
# These tests pin the behaviors landed in the email-extension correctness
# pass: snapshot+restore on suspend/resume, the new edit-profile and
# ack-handoff endpoints, the resend-handoff timestamp guard, and the
# onboarding-progress legend / new row actions surfaced in the payload.
# ----------------------------------------------------------------------


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailSuspendRestoreTests(unittest.TestCase):
    """Suspend snapshot+restore: a mailbox in a pre-operational state
    (``draft`` / empty) must NOT be promoted to ``operational`` by a
    Suspend → Resume round-trip. The prior state is snapshotted into
    ``workflow.lifecycle_state_prior_suspend`` on Suspend and restored
    on Resume.
    """

    def _build_client(self, lifecycle_state: str = "draft"):
        tmp = Path(tempfile.mkdtemp(prefix="email_correctness_suspend_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
            lifecycle_state=lifecycle_state,
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

    def test_resume_restores_pre_operational_state(self) -> None:
        client, aws_csm_dir = self._build_client(lifecycle_state="draft")
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
        # The mailbox was never operational; Resume must restore "draft",
        # not invent "operational" and falsify the onboarding count.
        self.assertEqual(body["lifecycle_state"], "draft")
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(on_disk["workflow"]["lifecycle_state"], "draft")
        # Snapshot key is cleared after restore so it doesn't accumulate.
        self.assertNotIn("lifecycle_state_prior_suspend", on_disk["workflow"])


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailEditProfileRouteTests(unittest.TestCase):
    """POST /__fnd/email/admin/edit-profile updates send_as_email, role,
    and operator_inbox_target on the AWS-CSM profile JSON. The mailbox
    local part is intentionally NOT editable.
    """

    def _build_client(self):
        tmp = Path(tempfile.mkdtemp(prefix="email_correctness_edit_"))
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

    def test_edit_profile_persists_changes(self) -> None:
        client, aws_csm_dir = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "send_as_email": "support+new@alpha.example.test",
                "role": "primary",
                "operator_inbox_target": "ops@alpha.example.test",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(
            sorted(body["changed_fields"]),
            ["operator_inbox_target", "role", "send_as_email"],
        )
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        ident = on_disk["identity"]
        self.assertEqual(ident["send_as_email"], "support+new@alpha.example.test")
        self.assertEqual(ident["role"], "primary")
        self.assertEqual(ident["operator_inbox_target"], "ops@alpha.example.test")
        # mailbox_local_part untouched.
        self.assertEqual(ident["mailbox_local_part"], "support")

    def test_edit_profile_ignores_mailbox_local_part_in_body(self) -> None:
        client, aws_csm_dir = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "mailbox_local_part": "renamed",
                "role": "primary",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        # mailbox_local_part is not in the editable_keys allowlist, so
        # it is silently dropped — role was the only honored field.
        self.assertEqual(resp.get_json()["changed_fields"], ["role"])
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(on_disk["identity"]["mailbox_local_part"], "support")

    def test_edit_profile_rejects_blank_send_as_email(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "send_as_email": "",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_field")

    def test_edit_profile_rejects_malformed_send_as_email(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({
                "profile_id": "aws-csm.alpha.support",
                "send_as_email": "no-at-sign",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_field")

    def test_edit_profile_rejects_when_no_editable_fields_supplied(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "no_changes")

    def test_edit_profile_rejects_missing_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({"role": "primary"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "missing_profile_id")

    def test_edit_profile_rejects_unknown_profile_id(self) -> None:
        client, _ = self._build_client()
        resp = client.post(
            "/__fnd/email/admin/edit-profile",
            data=json.dumps({
                "profile_id": "aws-csm.ghost.mailbox",
                "role": "primary",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"], "profile_not_found")


@unittest.skipUnless(FLASK_AVAILABLE, "Flask not installed in this environment")
class EmailAckHandoffRouteTests(unittest.TestCase):
    """POST /__fnd/email/admin/ack-handoff stamps ``handoff_acked_at`` so
    the onboarding-progress ``handoff_acked`` step keys on an explicit
    operator action instead of being inferred from lifecycle_state.
    """

    def _seed_with_handoff(self, lifecycle_state: str = "draft", *,
                           handoff_acked_at: str = "") -> tuple:
        tmp = Path(tempfile.mkdtemp(prefix="email_correctness_ack_"))
        for sub in ("public", "private", "data", "webapps"):
            (tmp / sub).mkdir()
        aws_csm_dir = tmp / "private" / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
            lifecycle_state=lifecycle_state,
        )
        # Patch in the handoff_email_sent_at marker so the ack gate opens.
        path = aws_csm_dir / "aws-csm.alpha.support.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        body["workflow"]["handoff_email_sent_at"] = "2026-05-22T12:00:00Z"
        if handoff_acked_at:
            body["workflow"]["handoff_acked_at"] = handoff_acked_at
        path.write_text(json.dumps(body), encoding="utf-8")
        config = V2PortalHostConfig(
            portal_instance_id="fnd",
            public_dir=tmp / "public",
            private_dir=tmp / "private",
            data_dir=tmp / "data",
            portal_domain="example.test",
            webapps_root=tmp / "webapps",
        )
        return create_app(config).test_client(), aws_csm_dir

    def test_ack_handoff_stamps_timestamp(self) -> None:
        client, aws_csm_dir = self._seed_with_handoff()
        resp = client.post(
            "/__fnd/email/admin/ack-handoff",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        body = resp.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["handoff_acked_at"])  # ISO-8601 stamp
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            on_disk["workflow"]["handoff_acked_at"], body["handoff_acked_at"]
        )

    def test_ack_handoff_advances_onboarding_progress(self) -> None:
        client, aws_csm_dir = self._seed_with_handoff()
        client.post(
            "/__fnd/email/admin/ack-handoff",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        # Re-load the JSON and recompute progress directly: handoff_acked
        # must now be in the completed set.
        on_disk = json.loads(
            (aws_csm_dir / "aws-csm.alpha.support.json").read_text(encoding="utf-8")
        )
        self.assertTrue(on_disk["workflow"]["handoff_acked_at"])
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _onboarding_progress,
        )
        progress = _onboarding_progress(on_disk)
        self.assertIn("handoff_acked", progress["completed"])
        self.assertIn("handoff_sent", progress["completed"])

    def test_ack_handoff_refuses_without_handoff_sent(self) -> None:
        # Seed without handoff_email_sent_at by clearing it post-seed.
        tmp = Path(tempfile.mkdtemp(prefix="email_correctness_ack_no_handoff_"))
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
        client = create_app(config).test_client()
        resp = client.post(
            "/__fnd/email/admin/ack-handoff",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        body = resp.get_json()
        self.assertEqual(body["error"], "not_eligible")
        self.assertEqual(body["detail"], "handoff_not_sent")

    def test_ack_handoff_refuses_double_ack(self) -> None:
        client, _ = self._seed_with_handoff(
            handoff_acked_at="2026-05-23T08:00:00Z"
        )
        resp = client.post(
            "/__fnd/email/admin/ack-handoff",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.get_json()["error"], "already_acked")

    def test_ack_handoff_refuses_suspended(self) -> None:
        client, _ = self._seed_with_handoff(lifecycle_state="suspended")
        resp = client.post(
            "/__fnd/email/admin/ack-handoff",
            data=json.dumps({"profile_id": "aws-csm.alpha.support"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        body = resp.get_json()
        self.assertEqual(body["error"], "not_eligible")
        self.assertEqual(body["detail"], "lifecycle=suspended")


class EmailExtensionPayloadCorrectnessTests(unittest.TestCase):
    """Payload-shape pins for the legend + new actions + uniform shape
    when private_dir is None.
    """

    def _payload_for(
        self, *, lifecycle_state: str = "draft", handoff_sent: bool = True,
        acked: bool = False,
    ):
        tmp = Path(tempfile.mkdtemp(prefix="email_correctness_payload_"))
        aws_csm_dir = tmp / "utilities" / "tools" / "aws-csm"
        path = _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
            lifecycle_state=lifecycle_state,
        )
        body = json.loads(path.read_text(encoding="utf-8"))
        if handoff_sent:
            body["workflow"]["handoff_email_sent_at"] = "2026-05-22T12:00:00Z"
        if acked:
            body["workflow"]["handoff_acked_at"] = "2026-05-23T08:00:00Z"
        path.write_text(json.dumps(body), encoding="utf-8")
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _build_email_extension_payload,
        )
        return _build_email_extension_payload(
            grantee={"domains": ["alpha.example.test"]},
            domain="alpha.example.test",
            private_dir=tmp,
        )

    def test_payload_includes_onboarding_steps_legend(self) -> None:
        payload = self._payload_for()
        steps = payload.get("onboarding_steps") or []
        self.assertEqual(len(steps), 6)
        keys = [s["key"] for s in steps]
        self.assertEqual(
            keys,
            [
                "profile_created",
                "ses_identity_ready",
                "handoff_sent",
                "handoff_acked",
                "inbound_configured",
                "inbound_verified",
            ],
        )

    def test_non_suspended_row_carries_edit_action(self) -> None:
        payload = self._payload_for(lifecycle_state="draft")
        profile = (payload.get("profiles") or [])[0]
        edit_action = profile.get("edit_profile_action") or {}
        self.assertEqual(edit_action.get("route"), "/__fnd/email/admin/edit-profile")
        self.assertTrue(edit_action.get("is_form"))
        keys = {f["key"] for f in edit_action.get("form_fields") or []}
        self.assertEqual(
            keys, {"send_as_email", "role", "operator_inbox_target"}
        )

    def test_suspended_row_omits_edit_action(self) -> None:
        payload = self._payload_for(lifecycle_state="suspended")
        profile = (payload.get("profiles") or [])[0]
        self.assertEqual(profile.get("edit_profile_action") or {}, {})

    def test_ack_action_visible_when_handoff_sent_and_not_acked(self) -> None:
        payload = self._payload_for(handoff_sent=True, acked=False)
        profile = (payload.get("profiles") or [])[0]
        ack = profile.get("ack_handoff_action") or {}
        self.assertEqual(ack.get("route"), "/__fnd/email/admin/ack-handoff")

    def test_ack_action_hidden_after_ack(self) -> None:
        payload = self._payload_for(handoff_sent=True, acked=True)
        profile = (payload.get("profiles") or [])[0]
        self.assertEqual(profile.get("ack_handoff_action") or {}, {})

    def test_ack_action_hidden_when_no_handoff(self) -> None:
        payload = self._payload_for(handoff_sent=False)
        profile = (payload.get("profiles") or [])[0]
        self.assertEqual(profile.get("ack_handoff_action") or {}, {})

    def test_handoff_acked_no_longer_inferred_from_lifecycle(self) -> None:
        # Operational lifecycle but no is_mailbox_operational and no
        # explicit ack timestamp — the handoff_acked step must read False.
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _onboarding_progress,
        )
        progress = _onboarding_progress({
            "workflow": {
                "lifecycle_state": "operational",
                "handoff_email_sent_at": "2026-05-22T12:00:00Z",
            },
        })
        self.assertNotIn("handoff_acked", progress["completed"])

    def test_handoff_acked_set_by_explicit_timestamp(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _onboarding_progress,
        )
        progress = _onboarding_progress({
            "workflow": {
                "handoff_email_sent_at": "2026-05-22T12:00:00Z",
                "handoff_acked_at": "2026-05-23T08:00:00Z",
            },
        })
        self.assertIn("handoff_acked", progress["completed"])
        self.assertIn("handoff_sent", progress["completed"])

    def test_private_dir_none_returns_uniform_shape(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _build_email_extension_payload,
        )
        payload = _build_email_extension_payload(
            grantee={"domains": ["alpha.example.test"]},
            domain="alpha.example.test",
            private_dir=None,
        )
        for key in ("profiles", "domains", "domain_record", "configuration",
                    "onboarding_steps", "notice"):
            self.assertIn(key, payload)
        self.assertEqual(payload["profiles"], [])
        self.assertEqual(payload["domain_record"], {})
        self.assertIn("Private directory not configured", payload["notice"])


if __name__ == "__main__":
    unittest.main()
