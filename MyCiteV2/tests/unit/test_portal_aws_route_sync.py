from __future__ import annotations

import json
import os
import sys
import unittest
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import (
    _apply_action,
    _profile_onboarding_projection,
    run_portal_aws_csm,
    run_portal_aws_csm_action,
)
from MyCiteV2.packages.state_machine.nimm import NimmDirective, NimmDirectiveEnvelope
from MyCiteV2.packages.state_machine.portal_shell import PortalScope


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_minimal_aws_csm_state(private_dir: Path) -> None:
    tool_root = private_dir / "utilities" / "tools" / "aws-csm"
    _write_json(private_dir / "config.json", {"msn_id": "3-2-3-17-77-1-6-4-1-4"})
    _write_json(
        tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json",
        {
            "schema": "mycite.portal.tool_collection.v1",
            "member_files": [
                "spec.json",
                "aws-csm-domain.cvccboard.json",
            ],
        },
    )
    _write_json(
        tool_root / "spec.json",
        {
            "schema": "mycite.portal.tool_mediation.v1",
            "tool_id": "aws_csm",
            "label": "AWS-CSM",
        },
    )
    _write_json(
        tool_root / "aws-csm-domain.cvccboard.json",
        {
            "schema": "mycite.service_tool.aws_csm.domain.v1",
            "identity": {
                "tenant_id": "cvccboard",
                "domain": "cvccboard.org",
                "region": "us-east-1",
                "hosted_zone_id": "Z05968042395KDRPX4PLG",
            },
            "dns": {
                "hosted_zone_present": True,
                "nameserver_match": True,
                "mx_record_present": True,
                "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"],
                "dkim_records_present": True,
                "dkim_record_values": [
                    "token-1.dkim.amazonses.com",
                    "token-2.dkim.amazonses.com",
                    "token-3.dkim.amazonses.com",
                ],
                "registrar_nameservers": [],
                "hosted_zone_nameservers": [],
            },
            "ses": {
                "identity_exists": True,
                "identity_status": "verified",
                "verified_for_sending_status": True,
                "dkim_status": "verified",
                "dkim_tokens": ["token-1", "token-2", "token-3"],
            },
            "receipt": {
                "status": "ok",
                "rule_name": "portal-capture-cvccboard-org",
                "expected_recipient": "cvccboard.org",
                "expected_lambda_name": "newsletter-inbound-capture",
                "bucket": "ses-inbound-fnd-mail",
                "prefix": "inbound/cvccboard.org/",
            },
            "observation": {"last_checked_at": "2026-04-20T00:00:00+00:00"},
        },
    )


def _domain_state_path(private_dir: Path) -> Path:
    return private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm-domain.cvccboard.json"


class _RouteSyncCloudSuccess:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, object]]] = []

    def sync_verification_route_map(self, *, profiles: list[dict[str, object]]) -> dict[str, object]:
        self.calls.append(list(profiles))
        tracked = sorted(
            str((dict(row.get("identity") or {})).get("send_as_email") or "").lower()
            for row in profiles
            if isinstance(row, dict)
        )
        return {
            "status": "success",
            "message": "Verification-forward route map synced to Lambda environment.",
            "route_count": len(tracked),
            "tracked_recipients": tracked,
            "lambda_name": "newsletter-inbound-capture",
            "changed": True,
        }


class _RouteSyncCloudFailure:
    def sync_verification_route_map(self, *, profiles: list[dict[str, object]]) -> dict[str, object]:
        _ = profiles
        raise ValueError("lambda:update_function_configuration access denied")


def _onboarding_payload(
    *,
    handoff_status: str = "not_started",
    verification_state: str = "not_started",
    provider_state: str = "not_started",
    inbound_state: str = "receive_unconfigured",
    secret_state: str = "missing",
    handoff_ready: bool = False,
    staging_state: str = "",
    handoff_sent_at: str = "",
    handoff_template_version: str = "",
    handoff_correction_sent_at: str = "",
    handoff_correction_required: bool | None = None,
    email_received_at: str = "",
    ready_for_user_handoff: bool = False,
    receive_verified: bool = False,
    mailbox_operational: bool = False,
) -> dict[str, object]:
    workflow: dict[str, object] = {
        "handoff_status": handoff_status,
        "handoff_email_sent_at": handoff_sent_at,
        "handoff_template_version": handoff_template_version,
        "handoff_correction_sent_at": handoff_correction_sent_at,
        "is_ready_for_user_handoff": ready_for_user_handoff,
        "is_mailbox_operational": mailbox_operational,
    }
    if handoff_correction_required is not None:
        workflow["handoff_correction_required"] = handoff_correction_required
    return {
        "workflow": workflow,
        "verification": {
            "portal_state": verification_state,
            "status": verification_state,
            "email_received_at": email_received_at,
        },
        "provider": {"send_as_provider_status": provider_state},
        "smtp": {
            "credentials_secret_state": secret_state,
            "handoff_ready": handoff_ready,
            "staging_state": staging_state,
        },
        "inbound": {
            "receive_state": inbound_state,
            "receive_verified": receive_verified,
        },
    }


class _DomainConvergenceCloud:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def ensure_domain_identity(self, domain_record: dict[str, object]) -> None:
        _ = domain_record
        self.calls.append("ensure_domain_identity")

    def sync_domain_dns(self, domain_record: dict[str, object]) -> None:
        _ = domain_record
        self.calls.append("sync_domain_dns")

    def ensure_domain_receipt_rule(self, domain_record: dict[str, object]) -> None:
        _ = domain_record
        self.calls.append("ensure_domain_receipt_rule")

    def describe_domain_status(self, domain_record: dict[str, object]) -> dict[str, object]:
        identity = dict(domain_record.get("identity") or {})
        return {
            "identity": identity,
            "dns": {
                "hosted_zone_present": True,
                "nameserver_match": True,
                "mx_record_present": True,
                "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"],
                "dkim_records_present": True,
                "dkim_record_values": [
                    "token-1.dkim.amazonses.com",
                    "token-2.dkim.amazonses.com",
                    "token-3.dkim.amazonses.com",
                ],
                "registrar_nameservers": [],
                "hosted_zone_nameservers": [],
            },
            "ses": {
                "identity_exists": True,
                "identity_status": "verified",
                "verified_for_sending_status": True,
                "dkim_status": "verified",
                "dkim_tokens": ["token-1", "token-2", "token-3"],
            },
            "receipt": {
                "status": "ok",
                "rule_name": "portal-capture-cvccboard-org",
                "expected_recipient": "cvccboard.org",
                "expected_lambda_name": "newsletter-inbound-capture",
                "bucket": "ses-inbound-fnd-mail",
                "prefix": "inbound/cvccboard.org/",
            },
            "observation": {"last_checked_at": "2026-04-23T00:00:00+00:00"},
        }


class _FakeNewsletterState:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def list_newsletter_domains(self) -> list[str]:
        self.calls.append(("list_newsletter_domains", ""))
        return ["cvccboard.org"]

    def load_profile(self, *, domain: str) -> dict[str, object]:
        self.calls.append(("load_profile", domain))
        return {
            "schema": "mycite.service_tool.aws_csm.newsletter_profile.v1",
            "domain": domain,
            "list_address": f"news@{domain}",
            "sender_address": f"news@{domain}",
            "selected_author_profile_id": "aws-csm.cvccboard.alex",
            "selected_author_address": f"alex@{domain}",
            "delivery_mode": "inbound-mail-workflow",
            "last_dispatch_id": "dispatch-1",
            "last_inbound_status": "ok",
            "last_inbound_subject": "Welcome",
        }

    def load_contact_log(self, *, domain: str) -> dict[str, object]:
        self.calls.append(("load_contact_log", domain))
        return {
            "schema": "mycite.service_tool.aws_csm.newsletter_contacts.v1",
            "domain": domain,
            "contacts": [
                {"email": "reader1@example.com", "subscribed": True},
                {"email": "reader2@example.com", "subscribed": False},
            ],
            "dispatches": [{"dispatch_id": "dispatch-1"}],
        }


class PortalAwsRouteSyncTests(unittest.TestCase):
    def test_profile_onboarding_projection_exposes_pending_staged_forwarded_confirmed_and_onboard(self) -> None:
        self.assertEqual(_profile_onboarding_projection(_onboarding_payload())["state"], "pending")
        self.assertEqual(
            _profile_onboarding_projection(
                _onboarding_payload(
                    handoff_status="ready_for_gmail_handoff",
                    provider_state="not_started",
                    verification_state="not_started",
                    secret_state="configured",
                    handoff_ready=True,
                    staging_state="material_ready",
                )
            )["state"],
            "staged",
        )
        self.assertEqual(
            _profile_onboarding_projection(
                _onboarding_payload(
                    handoff_status="instruction_sent",
                    handoff_sent_at="2026-04-24T00:00:00+00:00",
                    verification_state="capture_requested",
                )
            )["state"],
            "forwarded",
        )
        self.assertEqual(
            _profile_onboarding_projection(
                _onboarding_payload(
                    handoff_status="instruction_sent",
                    provider_state="verified",
                    verification_state="verified",
                )
            )["state"],
            "confirmed",
        )
        self.assertEqual(
            _profile_onboarding_projection(
                _onboarding_payload(
                    handoff_status="send_as_confirmed",
                    provider_state="verified",
                    verification_state="verified",
                    ready_for_user_handoff=True,
                )
            )["state"],
            "onboard",
        )

    def test_profile_onboarding_projection_marks_initiated_draft_as_pending_with_initiated_summary(self) -> None:
        payload = _onboarding_payload()
        payload["workflow"]["initiated"] = True
        payload["workflow"]["initiated_at"] = "2026-05-02T00:00:00+00:00"
        projected = _profile_onboarding_projection(payload)
        self.assertEqual(projected["state"], "pending")
        self.assertEqual(
            projected["summary"],
            "Mailbox onboarding is initiated; stage SMTP material to continue operator handoff.",
        )

    def test_actions_fail_closed_when_runtime_dependency_is_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime.importlib.util.find_spec",
                return_value=None,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "section": "users"},
                    action_kind="create_domain",
                    action_payload={
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "hosted_zone_id": "Z05968042395KDRPX4PLG",
                    },
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

        self.assertEqual(action_result["status"], "error")
        self.assertEqual(action_result["code"], "runtime_dependency_missing")
        self.assertIn("required_modules", action_result["details"])

    def test_create_profile_records_route_sync_success_details(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            cloud = _RouteSyncCloudSuccess()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=cloud,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "section": "users"},
                    action_kind="create_profile",
                    action_payload={
                        "domain": "cvccboard.org",
                        "mailbox_local_part": "alex",
                        "single_user_email": "alex@example.com",
                        "operator_inbox_target": "ops@example.com",
                    },
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

        self.assertEqual(action_result["status"], "accepted")
        details = action_result["details"]
        self.assertEqual(details["route_sync_status"], "success")
        self.assertEqual(details["route_sync_lambda_name"], "newsletter-inbound-capture")
        self.assertEqual(details["route_sync_changed"], "true")
        self.assertEqual(len(cloud.calls), 1)

    def test_create_domain_runs_full_domain_convergence_steps(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            cloud = _DomainConvergenceCloud()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime.importlib.util.find_spec",
                return_value=object(),
            ), patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=cloud,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains"},
                    action_kind="create_domain",
                    action_payload={
                        "tenant_id": "freshboard",
                        "domain": "freshboard.org",
                        "hosted_zone_id": "Z1234567890",
                        "region": "us-east-1",
                    },
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["readiness_state"], "ready_for_mailboxes")
        self.assertEqual(
            action_result["details"]["convergence_steps"],
            ["ensure_domain_identity", "sync_domain_dns", "ensure_domain_receipt_rule"],
        )
        self.assertEqual(cloud.calls, ["ensure_domain_identity", "sync_domain_dns", "ensure_domain_receipt_rule"])

    def test_create_profile_keeps_action_accepted_when_route_sync_warns(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=_RouteSyncCloudFailure(),
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "section": "users"},
                    action_kind="create_profile",
                    action_payload={
                        "domain": "cvccboard.org",
                        "mailbox_local_part": "alex",
                        "single_user_email": "alex@example.com",
                        "operator_inbox_target": "ops@example.com",
                    },
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

        self.assertEqual(action_result["status"], "accepted")
        details = action_result["details"]
        self.assertEqual(details["route_sync_status"], "warning")
        self.assertIn("deploy_aws_csm_pass3_inbound_capture.py", details["route_sync_manual_step"])

    def test_update_profile_rekeys_mailbox_and_resets_onboarding_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            tool_root = private_dir / "utilities" / "tools" / "aws-csm"
            collection_path = tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"
            collection = json.loads(collection_path.read_text(encoding="utf-8"))
            collection["member_files"].append("aws-csm.cvccboard.alexs.json")
            collection_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
            profile_path = tool_root / "aws-csm.cvccboard.alexs.json"
            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alexs",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "region": "us-east-1",
                        "mailbox_local_part": "alexs",
                        "role": "operator",
                        "single_user_email": "alex@example.com",
                        "operator_inbox_target": "ops@example.com",
                        "handoff_provider": "gmail",
                        "send_as_email": "alexs@cvccboard.org",
                    },
                    "smtp": {
                        "host": "email-smtp.us-east-1.amazonaws.com",
                        "port": "587",
                        "username": "SMTPUSER",
                        "credentials_secret_name": "aws-cms/smtp/cvccboard.alexs",
                        "credentials_secret_state": "configured",
                        "send_as_email": "alexs@cvccboard.org",
                        "local_part": "alexs",
                        "handoff_provider": "gmail",
                        "forward_to_email": "ops@example.com",
                        "handoff_ready": True,
                    },
                    "verification": {
                        "status": "verified",
                        "portal_state": "verified",
                        "verified_at": "2026-04-24T00:00:00+00:00",
                    },
                    "provider": {
                        "handoff_provider": "gmail",
                        "send_as_provider_status": "verified",
                        "gmail_send_as_status": "verified",
                        "aws_ses_identity_status": "verified",
                    },
                    "workflow": {
                        "lifecycle_state": "ready",
                        "handoff_status": "instruction_sent",
                        "is_ready_for_user_handoff": True,
                    },
                    "inbound": {
                        "receive_routing_target": "ops@example.com",
                        "receive_state": "receive_configured",
                        "receive_verified": True,
                    },
                },
            )

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=_RouteSyncCloudSuccess(),
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alexs", "section": "users"},
                    action_kind="update_profile",
                    action_payload={
                        "profile_id": "aws-csm.cvccboard.alexs",
                        "mailbox_local_part": "alex",
                        "single_user_email": "alex@example.com",
                        "operator_inbox_target": "ops@example.com",
                        "role": "operator",
                        "handoff_provider": "gmail",
                    },
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

            updated_path = tool_root / "aws-csm.cvccboard.alex.json"
            updated = json.loads(updated_path.read_text(encoding="utf-8"))
            old_exists = profile_path.exists()
            new_exists = updated_path.exists()

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["profile_id"], "aws-csm.cvccboard.alex")
        self.assertEqual(action_result["details"]["mailbox_identity_changed"], "true")
        self.assertFalse(old_exists)
        self.assertTrue(new_exists)
        self.assertEqual(updated["identity"]["send_as_email"], "alex@cvccboard.org")
        self.assertEqual(updated["smtp"]["credentials_secret_state"], "missing")
        self.assertEqual(updated["workflow"]["handoff_status"], "not_started")
        self.assertEqual(updated["verification"]["portal_state"], "not_started")

    def test_delete_profile_removes_file_and_syncs_routes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            tool_root = private_dir / "utilities" / "tools" / "aws-csm"
            collection_path = tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"
            collection = json.loads(collection_path.read_text(encoding="utf-8"))
            collection["member_files"].append("aws-csm.cvccboard.alex.json")
            collection_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
            profile_path = tool_root / "aws-csm.cvccboard.alex.json"
            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "smtp": {"forward_to_email": "ops@example.com"},
                    "workflow": {"lifecycle_state": "draft"},
                    "verification": {"portal_state": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "inbound": {"receive_state": "receive_unconfigured"},
                },
            )

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=_RouteSyncCloudSuccess(),
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex", "section": "users"},
                    action_kind="delete_profile",
                    action_payload={"profile_id": "aws-csm.cvccboard.alex"},
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

            collection = json.loads(collection_path.read_text(encoding="utf-8"))
            deleted = not profile_path.exists()

        self.assertEqual(action_result["status"], "accepted")
        self.assertTrue(deleted)
        self.assertNotIn("aws-csm.cvccboard.alex.json", collection["member_files"])

    def test_refresh_domain_status_reconciles_stale_domain_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            domain_path = _domain_state_path(private_dir)
            stale_domain = json.loads(domain_path.read_text(encoding="utf-8"))
            stale_domain["ses"] = {
                "identity_exists": False,
                "identity_status": "not_started",
                "verified_for_sending_status": False,
                "dkim_status": "not_started",
                "dkim_tokens": [],
            }
            stale_domain["dns"]["mx_record_present"] = False
            stale_domain["dns"]["dkim_records_present"] = False
            stale_domain["receipt"]["status"] = "not_ready"
            domain_path.write_text(json.dumps(stale_domain, indent=2) + "\n", encoding="utf-8")

            cloud = _DomainConvergenceCloud()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime.importlib.util.find_spec",
                return_value=object(),
            ), patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=cloud,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "section": "onboarding"},
                    action_kind="refresh_domain_status",
                    action_payload={"domain": "cvccboard.org"},
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

            reconciled = json.loads(domain_path.read_text(encoding="utf-8"))

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["readiness_state"], "ready_for_mailboxes")
        self.assertEqual(reconciled["readiness"]["state"], "ready_for_mailboxes")
        self.assertEqual(
            action_result["details"]["convergence_steps"],
            ["ensure_domain_identity", "sync_domain_dns", "ensure_domain_receipt_rule"],
        )

    def test_create_profile_fails_when_route_sync_fail_closed_is_enabled(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            with patch.dict(os.environ, {"AWS_CSM_ROUTE_SYNC_FAIL_CLOSED": "true"}, clear=False):
                with patch(
                    "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                    return_value=_RouteSyncCloudFailure(),
                ):
                    _, action_result = _apply_action(
                        portal_scope=PortalScope(scope_id="fnd"),
                        surface_query={"view": "domains", "domain": "cvccboard.org", "section": "users"},
                        action_kind="create_profile",
                        action_payload={
                            "domain": "cvccboard.org",
                            "mailbox_local_part": "alex",
                            "single_user_email": "alex@example.com",
                            "operator_inbox_target": "ops@example.com",
                        },
                        private_dir=private_dir,
                        audit_storage_file=None,
                    )

        self.assertEqual(action_result["status"], "error")
        self.assertEqual(action_result["code"], "action_failed")
        self.assertIn("route sync failed", action_result["message"].lower())

    def test_aws_csm_action_accepts_nimm_envelope_and_projects_lens_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            action_payload = {
                "domain": "cvccboard.org",
                "mailbox_local_part": "alex",
                "single_user_email": "ALEX@EXAMPLE.COM",
                "operator_inbox_target": "OPS@EXAMPLE.COM",
                "password": "SMTPPASS",
            }
            envelope = NimmDirectiveEnvelope(
                directive=NimmDirective(
                    verb="man",
                    target_authority="aws_csm",
                    targets=({"object_ref": "cvccboard.org"},),
                    payload={"action_kind": "create_profile", "action_payload": action_payload},
                ),
                aitas={"intention": "manipulate", "archetype": "aws_csm_onboarding", "scope": "test"},
            ).to_dict()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=_RouteSyncCloudSuccess(),
            ):
                response = run_portal_aws_csm_action(
                    {
                        "schema": "mycite.v2.portal.system.tools.aws_csm.action.request.v1",
                        "portal_scope": {"scope_id": "fnd"},
                        "surface_query": {"view": "domains", "domain": "cvccboard.org", "section": "users"},
                        "nimm_envelope": envelope,
                    },
                    private_dir=private_dir,
                )
            action_result = response["surface_payload"]["action_result"]
            compiled = action_result["nimm_envelope"]
            profile_id = action_result["created_profile"]["profile_id"]
            profile_path = private_dir / "utilities" / "tools" / "aws-csm" / f"{profile_id}.json"
            profile_text = profile_path.read_text(encoding="utf-8")
            details_text = json.dumps(action_result["details"], sort_keys=True)

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["mutation_lifecycle_action"], "apply")
        self.assertEqual(compiled["directive"]["target_authority"], "aws_csm")
        self.assertEqual(compiled["directive"]["verb"], "manipulate")
        self.assertEqual(compiled["directive"]["payload"]["action_payload"]["password"], "[redacted]")
        self.assertNotIn("SMTPPASS", profile_text)
        self.assertNotIn("SMTPPASS", details_text)
        lens_values = compiled["directive"]["payload"]["lens_values"]
        self.assertIn(
            {"field": "single_user_email", "lens_id": "email_address", "canonical_value": "alex@example.com", "validation_issues": ""},
            lens_values,
        )

    def test_runtime_surface_projects_deterministic_onboarding_states(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            profile_path = private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json"
            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "lifecycle_state": "draft",
                        "handoff_status": "ready_for_gmail_handoff",
                        "is_ready_for_user_handoff": True,
                    },
                    "verification": {
                        "portal_state": "not_started",
                        "status": "not_started",
                    },
                    "provider": {"send_as_provider_status": "not_started"},
                    "inbound": {"receive_state": "receive_unconfigured"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "staging_state": "material_ready",
                        "forward_to_email": "ops@example.com",
                    },
                },
            )

            staged_bundle = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                },
                private_dir=private_dir,
            )

            staged_workspace = staged_bundle["surface_payload"]["workspace"]
            self.assertEqual(staged_workspace["mailbox_rows"][0]["onboarding_state"], "staged")
            self.assertEqual(
                staged_workspace["selected_profile_onboarding"]["onboarding_state"],
                "staged",
            )

            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "lifecycle_state": "draft",
                        "handoff_status": "instruction_sent",
                        "handoff_email_sent_at": "2026-04-24T00:00:00+00:00",
                    },
                    "verification": {
                        "portal_state": "capture_requested",
                        "status": "capture_requested",
                    },
                    "provider": {"send_as_provider_status": "pending"},
                    "inbound": {"receive_state": "awaiting_message"},
                    "smtp": {"forward_to_email": "ops@example.com"},
                },
            )

            forwarded_bundle = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                },
                private_dir=private_dir,
            )

            forwarded_workspace = forwarded_bundle["surface_payload"]["workspace"]
            self.assertEqual(forwarded_workspace["mailbox_rows"][0]["onboarding_state"], "forwarded")
            self.assertEqual(
                forwarded_workspace["selected_profile_onboarding"]["onboarding_state"],
                "forwarded",
            )

            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "lifecycle_state": "draft",
                        "handoff_status": "send_as_confirmed",
                        "is_ready_for_user_handoff": True,
                    },
                    "verification": {
                        "portal_state": "verified",
                        "status": "verified",
                        "verified_at": "2026-04-24T00:00:00+00:00",
                    },
                    "provider": {"send_as_provider_status": "verified"},
                    "inbound": {"receive_state": "receive_pending"},
                    "smtp": {"forward_to_email": "ops@example.com"},
                },
            )

            onboard_bundle = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                },
                private_dir=private_dir,
            )

        onboard_workspace = onboard_bundle["surface_payload"]["workspace"]
        self.assertEqual(onboard_workspace["mailbox_rows"][0]["onboarding_state"], "onboard")
        self.assertEqual(
            onboard_workspace["selected_profile_onboarding"]["onboarding_state"],
            "onboard",
        )

    def test_runtime_surface_exposes_begin_onboarding_for_uninitiated_mailbox(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            profile_path = private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json"
            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "initiated": False,
                        "initiated_at": "",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {"forward_to_email": "alex@example.com"},
                    "inbound": {"receive_state": "receive_unconfigured"},
                },
            )

            bundle = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                },
                private_dir=private_dir,
            )

        actions = bundle["surface_payload"]["workspace"]["selected_profile_onboarding"]["actions"]
        begin_action = next(action for action in actions if action["kind"] == "begin_onboarding")
        self.assertTrue(begin_action["enabled"])
        self.assertEqual(begin_action["disabled_reason"], "")

    def test_run_portal_aws_csm_action_accepts_begin_onboarding_and_records_initiated_state(self) -> None:
        class _LocalOnboardingCloud:
            def supplemental_profile_patch(self, action: str, profile: dict[str, object]) -> dict[str, object]:
                _ = action, profile
                return {}

        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            profile_path = private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json"
            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "initiated": False,
                        "initiated_at": "",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {"forward_to_email": "alex@example.com"},
                    "inbound": {"receive_state": "receive_unconfigured"},
                },
            )

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=_LocalOnboardingCloud(),
            ):
                response = run_portal_aws_csm_action(
                    {
                        "schema": "mycite.v2.portal.system.tools.aws_csm.action.request.v1",
                        "portal_scope": {"scope_id": "fnd"},
                        "surface_query": {
                            "view": "domains",
                            "domain": "cvccboard.org",
                            "profile": "aws-csm.cvccboard.alex",
                            "section": "onboarding",
                        },
                        "action_kind": "begin_onboarding",
                        "action_payload": {"profile_id": "aws-csm.cvccboard.alex"},
                    },
                    private_dir=private_dir,
                )
            stored = json.loads(profile_path.read_text(encoding="utf-8"))

        action_result = response["surface_payload"]["action_result"]
        onboarding = response["surface_payload"]["workspace"]["selected_profile_onboarding"]
        begin_action = next(action for action in onboarding["actions"] if action["kind"] == "begin_onboarding")
        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["updated_sections"], ["workflow"])
        self.assertEqual(stored["workflow"]["initiated"], True)
        self.assertTrue(stored["workflow"]["initiated_at"])
        self.assertEqual(onboarding["onboarding_state"], "pending")
        self.assertEqual(
            onboarding["onboarding_summary"],
            "Mailbox onboarding is initiated; stage SMTP material to continue operator handoff.",
        )
        self.assertFalse(begin_action["enabled"])
        self.assertEqual(
            begin_action["disabled_reason"],
            "Onboarding was already initiated for this mailbox.",
        )

    def test_runtime_surface_projects_explicit_cuyahoga_domain_record(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            tool_root = private_dir / "utilities" / "tools" / "aws-csm"
            collection_path = tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"
            collection_payload = json.loads(collection_path.read_text(encoding="utf-8"))
            collection_payload["member_files"].append("aws-csm-domain.cvcc.json")
            _write_json(collection_path, collection_payload)
            _write_json(
                tool_root / "aws-csm-domain.cvcc.json",
                {
                    "schema": "mycite.service_tool.aws_csm.domain.v1",
                    "identity": {
                        "tenant_id": "cvcc",
                        "domain": "cuyahogavalleycountrysideconservancy.org",
                        "region": "us-east-1",
                        "hosted_zone_id": "Z09517872ZM94H1UQZ0MD",
                    },
                    "dns": {
                        "hosted_zone_present": True,
                        "nameserver_match": True,
                        "mx_record_present": True,
                        "mx_record_values": ["10 inbound-smtp.us-east-1.amazonaws.com"],
                        "dkim_records_present": True,
                        "dkim_record_values": [
                            "token-a.dkim.amazonses.com",
                            "token-b.dkim.amazonses.com",
                            "token-c.dkim.amazonses.com",
                        ],
                        "registrar_nameservers": [],
                        "hosted_zone_nameservers": [],
                    },
                    "ses": {
                        "identity_exists": True,
                        "identity_status": "verified",
                        "verified_for_sending_status": True,
                        "dkim_status": "success",
                        "dkim_tokens": ["token-a", "token-b", "token-c"],
                    },
                    "receipt": {
                        "status": "ok",
                        "rule_name": "portal-capture-cuyahogavalleycountrysideconservancy-org",
                        "expected_recipient": "cuyahogavalleycountrysideconservancy.org",
                        "expected_lambda_name": "newsletter-inbound-capture",
                        "bucket": "ses-inbound-fnd-mail",
                        "prefix": "inbound/cuyahogavalleycountrysideconservancy.org/",
                    },
                    "observation": {"last_checked_at": "2026-04-29T00:00:00+00:00"},
                    "readiness": {
                        "schema": "mycite.service_tool.aws_csm.domain_readiness.v1",
                        "state": "ready_for_mailboxes",
                        "summary": "Domain onboarding is ready for mailbox creation.",
                        "blockers": [],
                        "last_checked_at": "2026-04-29T00:00:00+00:00",
                        "domain": "cuyahogavalleycountrysideconservancy.org",
                    },
                },
            )

            bundle = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"view": "domains", "domain": "cuyahogavalleycountrysideconservancy.org"},
                },
                private_dir=private_dir,
            )

        workspace = bundle["surface_payload"]["workspace"]
        domain_row = next(row for row in workspace["domain_rows"] if row["domain"] == "cuyahogavalleycountrysideconservancy.org")
        self.assertEqual(domain_row["onboarding_state"], "ready_for_mailboxes")
        self.assertNotEqual(domain_row["onboarding_state"], "legacy_inferred")
        self.assertEqual(
            workspace["selected_domain_onboarding"]["readiness_state"],
            "ready_for_mailboxes",
        )

    def test_runtime_surface_projects_handoff_correction_posture_for_legacy_mailbox(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            _write_json(
                private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                        "operator_inbox_target": "alex@example.com",
                    },
                    "workflow": {
                        "handoff_status": "instruction_sent",
                        "handoff_email_sent_at": "2026-04-24T00:00:00+00:00",
                        "handoff_email_sent_to": "alex@example.com",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "pending"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "forward_to_email": "alex@example.com",
                    },
                    "inbound": {"receive_state": "receive_configured"},
                },
            )

            bundle = run_portal_aws_csm(
                {
                    "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                    "portal_scope": {"scope_id": "fnd"},
                    "surface_query": {"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                },
                private_dir=private_dir,
            )

        workspace = bundle["surface_payload"]["workspace"]
        onboarding = workspace["selected_profile_onboarding"]
        self.assertEqual(onboarding["handoff_template_version"], "legacy_unversioned")
        self.assertEqual(onboarding["handoff_correction_required"], "yes")
        self.assertEqual(onboarding["handoff_correction_status"], "required")
        correction_action = next(
            action for action in onboarding["actions"] if action["kind"] == "send_handoff_correction_email"
        )
        self.assertTrue(correction_action["enabled"])
        self.assertEqual(
            workspace["selected_domain_onboarding"]["handoff_correction_required_count"],
            "1",
        )

    def test_send_handoff_email_records_template_version_on_initial_send(self) -> None:
        class _InitialSendCloud:
            def send_handoff_email(self, profile: dict[str, object]) -> dict[str, object]:
                identity = dict(profile.get("identity") or {})
                return {
                    "message_id": "ses-message-001",
                    "sent_to": "alex@example.com",
                    "send_as_email": identity.get("send_as_email") or "",
                    "handoff_provider": "gmail",
                    "template_version": "smtp_credentials_v2_minimal_5field",
                }

        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            _write_json(
                private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {"handoff_status": "ready_for_gmail_handoff"},
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "forward_to_email": "alex@example.com",
                    },
                    "inbound": {"receive_state": "receive_unconfigured"},
                },
            )

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=_InitialSendCloud(),
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                    action_kind="send_handoff_email",
                    action_payload={"profile_id": "aws-csm.cvccboard.alex"},
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

            stored = json.loads(
                (
                    private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json"
                ).read_text(encoding="utf-8")
            )

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["template_version"], "smtp_credentials_v2_minimal_5field")
        self.assertEqual(
            stored["workflow"]["handoff_template_version"],
            "smtp_credentials_v2_minimal_5field",
        )
        self.assertFalse(stored["workflow"]["handoff_correction_required"])

    def test_send_handoff_correction_email_updates_correction_metadata(self) -> None:
        class _CorrectionCloud:
            def __init__(self) -> None:
                self.called = 0

            def send_handoff_correction_email(self, profile: dict[str, object]) -> dict[str, object]:
                self.called += 1
                identity = dict(profile.get("identity") or {})
                return {
                    "message_id": "ses-correction-001",
                    "sent_to": "alex@example.com",
                    "send_as_email": identity.get("send_as_email") or "",
                    "handoff_provider": "gmail",
                    "template_version": "smtp_credentials_v2_minimal_5field",
                }

        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            profile_path = private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json"
            _write_json(
                profile_path,
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "handoff_status": "instruction_sent",
                        "handoff_email_sent_to": "alex@example.com",
                        "handoff_email_sent_at": "2026-04-24T00:00:00+00:00",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "forward_to_email": "alex@example.com",
                    },
                    "inbound": {"receive_state": "receive_configured"},
                },
            )
            cloud = _CorrectionCloud()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=cloud,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                    action_kind="send_handoff_correction_email",
                    action_payload={"profile_id": "aws-csm.cvccboard.alex"},
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

            stored = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["template_version"], "smtp_credentials_v2_minimal_5field")
        self.assertEqual(cloud.called, 1)
        self.assertEqual(
            stored["workflow"]["handoff_template_version"],
            "smtp_credentials_v2_minimal_5field",
        )
        self.assertFalse(stored["workflow"]["handoff_correction_required"])
        self.assertEqual(stored["workflow"]["handoff_correction_sent_to"], "alex@example.com")
        self.assertEqual(stored["workflow"]["handoff_correction_message_id"], "ses-correction-001")
        self.assertTrue(stored["workflow"]["handoff_correction_sent_at"])
        self.assertEqual(stored["workflow"]["handoff_email_sent_to"], "alex@example.com")

    def test_send_pending_handoff_corrections_runs_domain_bulk_flow(self) -> None:
        class _BulkCorrectionCloud:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def send_handoff_correction_email(self, profile: dict[str, object]) -> dict[str, object]:
                identity = dict(profile.get("identity") or {})
                email = str(identity.get("send_as_email") or "")
                self.calls.append(email)
                return {
                    "message_id": "bulk-" + email,
                    "sent_to": str((dict(profile.get("smtp") or {})).get("forward_to_email") or ""),
                    "send_as_email": email,
                    "handoff_provider": "gmail",
                    "template_version": "smtp_credentials_v2_minimal_5field",
                }

        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            tool_root = private_dir / "utilities" / "tools" / "aws-csm"
            collection_path = tool_root / "tool.3-2-3-17-77-1-6-4-1-4.aws-csm.json"
            collection = json.loads(collection_path.read_text(encoding="utf-8"))
            collection["member_files"].extend(["aws-csm.cvccboard.alex.json", "aws-csm.cvccboard.jordan.json"])
            collection_path.write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
            _write_json(
                tool_root / "aws-csm.cvccboard.alex.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                    },
                    "workflow": {
                        "handoff_status": "instruction_sent",
                        "handoff_email_sent_to": "alex@example.com",
                        "handoff_email_sent_at": "2026-04-24T00:00:00+00:00",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "forward_to_email": "alex@example.com",
                    },
                    "inbound": {"receive_state": "receive_configured"},
                },
            )
            _write_json(
                tool_root / "aws-csm.cvccboard.jordan.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.jordan",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "jordan@cvccboard.org",
                    },
                    "workflow": {
                        "handoff_status": "instruction_sent",
                        "handoff_email_sent_to": "jordan@example.com",
                        "handoff_email_sent_at": "2026-04-24T00:00:00+00:00",
                        "handoff_template_version": "smtp_credentials_v2_minimal_5field",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "forward_to_email": "jordan@example.com",
                    },
                    "inbound": {"receive_state": "receive_configured"},
                },
            )
            cloud = _BulkCorrectionCloud()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime.importlib.util.find_spec",
                return_value=object(),
            ), patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=cloud,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "section": "onboarding"},
                    action_kind="send_pending_handoff_corrections",
                    action_payload={"domain": "cvccboard.org"},
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

            corrected = json.loads((tool_root / "aws-csm.cvccboard.alex.json").read_text(encoding="utf-8"))
            untouched = json.loads((tool_root / "aws-csm.cvccboard.jordan.json").read_text(encoding="utf-8"))

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["details"]["correction_count"], "1")
        self.assertEqual(cloud.calls, ["alex@cvccboard.org"])
        self.assertTrue(corrected["workflow"]["handoff_correction_sent_at"])
        self.assertFalse(corrected["workflow"]["handoff_correction_required"])
        self.assertNotIn("handoff_correction_sent_at", untouched["workflow"])

    def test_send_handoff_email_skips_resend_when_handoff_was_already_recorded(self) -> None:
        class _CloudGuard:
            def __init__(self) -> None:
                self.called = False

            def send_handoff_email(self, profile: dict[str, object]) -> dict[str, object]:
                _ = profile
                self.called = True
                raise AssertionError("send_handoff_email should be skipped when handoff is already recorded")

        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            _write_json(
                private_dir / "utilities" / "tools" / "aws-csm" / "aws-csm.cvccboard.alex.json",
                {
                    "schema": "mycite.service_tool.aws_csm.profile.v1",
                    "identity": {
                        "profile_id": "aws-csm.cvccboard.alex",
                        "tenant_id": "cvccboard",
                        "domain": "cvccboard.org",
                        "send_as_email": "alex@cvccboard.org",
                        "single_user_email": "alex@example.com",
                    },
                    "workflow": {
                        "handoff_status": "instruction_sent",
                        "handoff_email_sent_to": "alex@example.com",
                        "handoff_email_sent_at": "2026-04-29T00:00:00+00:00",
                    },
                    "verification": {"portal_state": "not_started", "status": "not_started"},
                    "provider": {"send_as_provider_status": "not_started"},
                    "smtp": {
                        "credentials_secret_state": "configured",
                        "handoff_ready": True,
                        "forward_to_email": "alex@example.com",
                    },
                    "inbound": {"receive_state": "receive_configured"},
                },
            )
            cloud = _CloudGuard()
            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._onboarding_cloud",
                return_value=cloud,
            ):
                _, action_result = _apply_action(
                    portal_scope=PortalScope(scope_id="fnd"),
                    surface_query={"view": "domains", "domain": "cvccboard.org", "profile": "aws-csm.cvccboard.alex"},
                    action_kind="send_handoff_email",
                    action_payload={"profile_id": "aws-csm.cvccboard.alex"},
                    private_dir=private_dir,
                    audit_storage_file=None,
                )

        self.assertEqual(action_result["status"], "accepted")
        self.assertEqual(action_result["code"], "handoff_already_sent")
        self.assertEqual(action_result["details"]["sent_to"], "alex@example.com")
        self.assertFalse(cloud.called)

    def test_workspace_renderer_source_defaults_to_onboarding_tabs_without_legacy_section_filters(self) -> None:
        source = (
            REPO_ROOT
            / "MyCiteV2"
            / "instances"
            / "_shared"
            / "portal_host"
            / "static"
            / "v2_portal_aws_workspace.js"
        ).read_text(encoding="utf-8")

        self.assertIn('{ id: "onboarding", label: "Onboarding", active: true }, { id: "domain", label: "Domain", active: true }', source)
        self.assertIn('activeInspectorTabId(tabs, "onboarding")', source)
        self.assertNotIn("data-aws-section", source)
        self.assertNotIn("data-aws-section-clear", source)
        self.assertIn("handoff_correction_status", source)
        self.assertIn("data-aws-domain-action-kind", source)
        self.assertLess(
            source.index('renderInspectorTabPanel("onboarding"'),
            source.index('renderInspectorTabPanel("domain"'),
        )

    def test_runtime_surface_reads_newsletter_metadata_through_adapter_helper(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir = Path(temp_dir)
            _write_minimal_aws_csm_state(private_dir)
            fake_state = _FakeNewsletterState()

            with patch(
                "MyCiteV2.instances._shared.runtime.portal_aws_runtime._newsletter_state",
                return_value=fake_state,
            ):
                bundle = run_portal_aws_csm(
                    {
                        "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                        "portal_scope": {"scope_id": "fnd"},
                        "surface_query": {"view": "domains", "domain": "cvccboard.org", "section": "newsletter"},
                    },
                    private_dir=private_dir,
                )

        workspace = bundle["surface_payload"]["workspace"]
        self.assertEqual(workspace["newsletter_domain_count"], 1)
        self.assertEqual(workspace["domain_rows"][0]["dispatch_count"], 1)
        self.assertTrue(workspace["domain_rows"][0]["newsletter_configured"])
        self.assertEqual(workspace["selected_newsletter"]["list_address"], "news@cvccboard.org")
        self.assertIn(("list_newsletter_domains", ""), fake_state.calls)
        self.assertIn(("load_profile", "cvccboard.org"), fake_state.calls)
        self.assertIn(("load_contact_log", "cvccboard.org"), fake_state.calls)

    def test_deployed_fnd_private_state_projects_current_aws_csm_surface_contract(self) -> None:
        deployed_private_dir = REPO_ROOT / "deployed" / "fnd" / "private"
        if not deployed_private_dir.exists():
            self.skipTest("deployed FND private state is not available in this checkout")

        bundle = run_portal_aws_csm(
            {
                "schema": "mycite.v2.portal.system.tools.aws_csm.request.v1",
                "portal_scope": {"scope_id": "fnd", "capabilities": ["portal.system.tools.aws_csm.view"]},
                "surface_query": {
                    "view": "domains",
                    "domain": "cvccboard.org",
                    "profile": "aws-csm.cvccboard.nathan",
                    "section": "onboarding",
                },
            },
            private_dir=deployed_private_dir,
        )

        surface_payload = bundle["surface_payload"]
        workspace = surface_payload["workspace"]
        fingerprints = surface_payload["source_surface_fingerprints"]
        expected_files = {
            "runtime_py": REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "runtime" / "portal_aws_runtime.py",
            "workspace_js": REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_aws_workspace.js",
            "onboarding_cloud_py": REPO_ROOT / "MyCiteV2" / "packages" / "adapters" / "event_transport" / "aws_csm_onboarding_cloud.py",
        }

        self.assertTrue(surface_payload["tool"]["configured"])
        self.assertTrue(surface_payload["tool"]["enabled"])
        self.assertEqual(surface_payload["action_contract"]["route"], "/portal/api/v2/system/tools/aws-csm/actions")
        self.assertEqual(surface_payload["runtime_dependency_baseline"]["required_modules"], ["boto3"])
        self.assertEqual(workspace["selected_domain"], "cvccboard.org")
        self.assertEqual(workspace["selected_domain_onboarding"]["readiness_state"], "ready_for_mailboxes")
        self.assertEqual(workspace["selected_profile_onboarding"]["onboarding_state"], "forwarded")
        self.assertEqual(
            workspace["selected_profile_onboarding"]["handoff"]["handoff_email_sent_to"],
            "n8seals@gmail.com",
        )
        for key, path in expected_files.items():
            self.assertEqual(fingerprints[key]["path"], str(path.relative_to(REPO_ROOT)))
            self.assertEqual(
                fingerprints[key]["sha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
