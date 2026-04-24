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
    handoff_sent_at: str = "",
    email_received_at: str = "",
    ready_for_user_handoff: bool = False,
    receive_verified: bool = False,
    mailbox_operational: bool = False,
) -> dict[str, object]:
    return {
        "workflow": {
            "handoff_status": handoff_status,
            "handoff_email_sent_at": handoff_sent_at,
            "is_ready_for_user_handoff": ready_for_user_handoff,
            "is_mailbox_operational": mailbox_operational,
        },
        "verification": {
            "portal_state": verification_state,
            "status": verification_state,
            "email_received_at": email_received_at,
        },
        "provider": {"send_as_provider_status": provider_state},
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
    def test_profile_onboarding_projection_exposes_pending_forwarded_confirmed_and_onboard(self) -> None:
        self.assertEqual(_profile_onboarding_projection(_onboarding_payload())["state"], "pending")
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
