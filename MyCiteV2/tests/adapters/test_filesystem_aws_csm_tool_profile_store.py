from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.filesystem import (
    AWS_CSM_DOMAIN_SCHEMA,
    FilesystemAwsCsmToolProfileStore,
)
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingProfileStorePort
from MyCiteV2.packages.ports.aws_csm_profile_registry import AwsCsmProfileRegistryPort


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _seed_profile() -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.fnd.dylan",
            "tenant_id": "fnd",
            "domain": "fruitfulnetworkdevelopment.com",
            "region": "us-east-1",
            "mailbox_local_part": "dylan",
            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
            "single_user_email": "dylan@fruitfulnetworkdevelopment.com",
        },
        "smtp": {"forward_to_email": "dylan@fruitfulnetworkdevelopment.com"},
        "workflow": {"lifecycle_state": "ready"},
        "verification": {"portal_state": "verified"},
        "provider": {"aws_ses_identity_status": "verified"},
        "inbound": {"receive_state": "receive_operational"},
    }


def _seed_domain(
    *,
    tenant_id: str = "fnd",
    domain: str = "fruitfulnetworkdevelopment.com",
    identity_status: str = "verified",
) -> dict[str, object]:
    return {
        "schema": AWS_CSM_DOMAIN_SCHEMA,
        "identity": {
            "tenant_id": tenant_id,
            "domain": domain,
            "region": "us-east-1",
            "hosted_zone_id": "Z1234567890",
        },
        "dns": {
            "hosted_zone_present": True,
            "nameserver_match": True,
            "registrar_nameservers": ["ns-1.example.com"],
            "hosted_zone_nameservers": ["ns-1.example.com"],
            "mx_expected_value": "10 inbound-smtp.us-east-1.amazonaws.com",
            "mx_record_present": identity_status == "verified",
            "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"] if identity_status == "verified" else [],
            "dkim_records_present": identity_status == "verified",
            "dkim_record_values": ["token-1.dkim.amazonses.com"] if identity_status == "verified" else [],
        },
        "ses": {
            "identity_exists": True,
            "identity_status": identity_status,
            "verified_for_sending_status": identity_status == "verified",
            "dkim_status": "verified" if identity_status == "verified" else "pending",
            "dkim_tokens": ["token-1", "token-2", "token-3"] if identity_status == "verified" else [],
        },
        "receipt": {
            "status": "ok" if identity_status == "verified" else "not_ready",
            "rule_name": f"portal-capture-{tenant_id}",
            "expected_recipient": domain,
            "expected_lambda_name": "newsletter-inbound-capture",
            "bucket": "ses-inbound-fnd-mail",
            "prefix": f"inbound/{domain}/",
        },
        "observation": {"last_checked_at": "2026-04-18T00:00:00+00:00"},
        "readiness": {
            "schema": "mycite.service_tool.aws_csm.domain_readiness.v1",
            "state": "ready_for_mailboxes" if identity_status == "verified" else "dns_pending",
            "summary": "",
            "blockers": [],
            "last_checked_at": "2026-04-18T00:00:00+00:00",
            "domain": domain,
        },
    }


class FilesystemAwsCsmToolProfileStoreTests(unittest.TestCase):
    def test_registry_creation_updates_collection_and_profile_loading(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {
                    "schema": "mycite.portal.tool_collection.v1",
                    "member_files": ["aws-csm.fnd.dylan.json"],
                },
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())

            adapter = FilesystemAwsCsmToolProfileStore(tool_root)
            self.assertIsInstance(adapter, AwsCsmProfileRegistryPort)
            self.assertIsInstance(adapter, AwsCsmOnboardingProfileStorePort)

            created = adapter.create_profile(
                profile_id="aws-csm.fnd.alex",
                payload={
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.fnd.alex",
                        "tenant_id": "fnd",
                        "domain": "fruitfulnetworkdevelopment.com",
                        "region": "us-east-1",
                        "mailbox_local_part": "alex",
                        "send_as_email": "alex@fruitfulnetworkdevelopment.com",
                        "single_user_email": "alex@example.com",
                    },
                    "smtp": {"forward_to_email": "ops@example.com"},
                    "workflow": {"lifecycle_state": "draft"},
                    "verification": {"portal_state": "not_started"},
                    "provider": {"gmail_send_as_status": "not_started"},
                    "inbound": {"receive_state": "receive_unconfigured"},
                },
            )

            self.assertEqual(created["identity"]["profile_id"], "aws-csm.fnd.alex")
            collection_payload = json.loads(
                (tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json").read_text(encoding="utf-8")
            )
            self.assertIn("aws-csm.fnd.alex.json", collection_payload["member_files"])
            loaded = adapter.load_profile(tenant_scope_id="fnd", profile_id="aws-csm.fnd.alex")
            self.assertEqual(loaded["identity"]["send_as_email"], "alex@fruitfulnetworkdevelopment.com")

    def test_save_profile_round_trips_for_onboarding_updates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {"schema": "mycite.portal.tool_collection.v1", "member_files": ["aws-csm.fnd.dylan.json"]},
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())
            adapter = FilesystemAwsCsmToolProfileStore(tool_root)

            payload = adapter.load_profile(tenant_scope_id="fruitfulnetworkdevelopment.com", profile_id="aws-csm.fnd.dylan")
            payload["workflow"]["handoff_status"] = "ready_for_gmail_handoff"
            payload["smtp"]["username"] = "SMTPUSER"
            saved = adapter.save_profile(
                tenant_scope_id="fruitfulnetworkdevelopment.com",
                profile_id="aws-csm.fnd.dylan",
                payload=payload,
            )

            self.assertEqual(saved["workflow"]["handoff_status"], "ready_for_gmail_handoff")
            self.assertEqual(saved["smtp"]["username"], "SMTPUSER")

    def test_domain_creation_updates_collection_and_loads_by_domain(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {"schema": "mycite.portal.tool_collection.v1", "member_files": ["aws-csm.fnd.dylan.json"]},
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())
            adapter = FilesystemAwsCsmToolProfileStore(tool_root)

            created = adapter.create_domain(
                tenant_id="cvccboard",
                payload=_seed_domain(tenant_id="cvccboard", domain="cvccboard.org", identity_status="not_started"),
            )

            self.assertEqual(created["identity"]["tenant_id"], "cvccboard")
            self.assertEqual(created["identity"]["domain"], "cvccboard.org")
            collection_payload = json.loads(
                (tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json").read_text(encoding="utf-8")
            )
            self.assertIn("aws-csm-domain.cvccboard.json", collection_payload["member_files"])
            loaded = adapter.load_domain(domain="cvccboard.org")
            self.assertEqual(loaded["identity"]["hosted_zone_id"], "Z1234567890")

    def test_save_domain_round_trips_status_updates(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {
                    "schema": "mycite.portal.tool_collection.v1",
                    "member_files": ["aws-csm-domain.cvccboard.json"],
                },
            )
            _write_json(tool_root / "aws-csm-domain.cvccboard.json", _seed_domain(tenant_id="cvccboard", domain="cvccboard.org"))
            adapter = FilesystemAwsCsmToolProfileStore(tool_root)

            payload = adapter.load_domain(domain="cvccboard.org")
            payload["receipt"]["status"] = "ok"
            payload["observation"]["last_checked_at"] = "2026-04-18T12:00:00+00:00"
            saved = adapter.save_domain(domain="cvccboard.org", payload=payload)

            self.assertEqual(saved["receipt"]["status"], "ok")
            self.assertEqual(saved["observation"]["last_checked_at"], "2026-04-18T12:00:00+00:00")

    def test_resolve_domain_seed_prefers_explicit_domain_record(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {
                    "schema": "mycite.portal.tool_collection.v1",
                    "member_files": ["aws-csm.fnd.dylan.json", "aws-csm-domain.cvccboard.json"],
                },
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())
            _write_json(tool_root / "aws-csm-domain.cvccboard.json", _seed_domain(tenant_id="cvccboard", domain="fruitfulnetworkdevelopment.com", identity_status="not_started"))
            adapter = FilesystemAwsCsmToolProfileStore(tool_root)

            seed = adapter.resolve_domain_seed(domain="fruitfulnetworkdevelopment.com")

            self.assertEqual(seed["tenant_id"], "cvccboard")
            self.assertEqual(seed["provider"]["aws_ses_identity_status"], "not_started")

    def test_resolve_domain_seed_falls_back_to_mailbox_profile_when_domain_record_is_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            tool_root = Path(temp_dir)
            _write_json(
                tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
                {"schema": "mycite.portal.tool_collection.v1", "member_files": ["aws-csm.fnd.dylan.json"]},
            )
            _write_json(tool_root / "aws-csm.fnd.dylan.json", _seed_profile())
            adapter = FilesystemAwsCsmToolProfileStore(tool_root)

            seed = adapter.resolve_domain_seed(domain="fruitfulnetworkdevelopment.com")

            self.assertEqual(seed["tenant_id"], "fnd")
            self.assertEqual(seed["provider"]["aws_ses_identity_status"], "verified")


if __name__ == "__main__":
    unittest.main()
