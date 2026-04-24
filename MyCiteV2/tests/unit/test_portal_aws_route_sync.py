from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.portal_aws_runtime import _apply_action
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


class PortalAwsRouteSyncTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
