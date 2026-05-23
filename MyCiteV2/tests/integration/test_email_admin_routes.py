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


class EmailExtensionPayloadEditAndLegendTests(unittest.TestCase):
    """2026-05-23 — payload-shape pins for the inline-edit action +
    Remove action + onboarding legend table.
    """

    def _payload_with_profile(self):
        tmp = Path(tempfile.mkdtemp(prefix="2026_05_23_email_payload_"))
        aws_csm_dir = tmp / "utilities" / "tools" / "aws-csm"
        _seed_profile(
            aws_csm_dir,
            "aws-csm.alpha.support",
            tenant_id="alpha",
            domain="alpha.example.test",
            mailbox="support",
        )
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _build_email_extension_payload,
        )
        return _build_email_extension_payload(
            grantee={},
            domain="alpha.example.test",
            private_dir=tmp,
        )

    def test_profile_row_carries_edit_action(self) -> None:
        payload = self._payload_with_profile()
        profiles = payload.get("profiles") or []
        self.assertTrue(profiles)
        edit = profiles[0].get("edit_action") or {}
        self.assertEqual(edit.get("label"), "Edit")
        self.assertEqual(edit.get("route"), "/__fnd/email/admin/edit")
        keys = {f["key"] for f in edit.get("editable_fields") or []}
        self.assertEqual(keys, {"send_as_email", "role", "operator_inbox_target"})

    def test_profile_row_carries_remove_action(self) -> None:
        payload = self._payload_with_profile()
        profiles = payload.get("profiles") or []
        remove = profiles[0].get("remove_action") or {}
        self.assertEqual(remove.get("label"), "Remove")
        self.assertEqual(remove.get("route"), "/__fnd/email/admin/remove")
        self.assertEqual(remove.get("variant"), "danger")
        self.assertIn("Remove profile", remove.get("confirm", ""))

    def test_onboarding_legend_table_is_six_steps(self) -> None:
        payload = self._payload_with_profile()
        legend = payload.get("onboarding_legend") or []
        self.assertEqual(len(legend), 6)
        # Step ordering matches the progress bar denominator.
        self.assertEqual([r["step"] for r in legend], ["1", "2", "3", "4", "5", "6"])
        keys = [r["key"] for r in legend]
        self.assertEqual(keys[0], "profile_created")
        self.assertEqual(keys[-1], "inbound_verified")
        # Every step has a non-empty meaning string.
        for row in legend:
            self.assertTrue(row.get("meaning"), f"empty meaning for {row.get('key')}")

    def test_onboarding_legend_present_when_no_profiles(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="2026_05_23_email_empty_"))
        (tmp / "utilities" / "tools" / "aws-csm").mkdir(parents=True)
        from MyCiteV2.instances._shared.runtime.utilities_extensions.email import (
            _build_email_extension_payload,
        )
        payload = _build_email_extension_payload(
            grantee={"domains": ["empty.example.test"]},
            domain="empty.example.test",
            private_dir=tmp,
        )
        self.assertEqual(payload.get("profiles"), [])
        self.assertEqual(len(payload.get("onboarding_legend") or []), 6)


if __name__ == "__main__":
    unittest.main()
