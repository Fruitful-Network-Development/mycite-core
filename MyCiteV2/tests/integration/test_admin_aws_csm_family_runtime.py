from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.instances._shared.runtime.admin_aws_runtime import (
    run_admin_aws_csm_family_home,
    run_admin_aws_csm_newsletter,
)
from MyCiteV2.instances._shared.runtime.runtime_platform import (
    ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA,
    ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA,
    ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE,
    build_admin_tool_exposure_policy,
)


def _tool_exposure_policy(*, newsletter_enabled: bool = True) -> dict[str, object]:
    return build_admin_tool_exposure_policy(
        {
            "aws": {"enabled": True},
            "aws_csm_newsletter": {"enabled": newsletter_enabled},
            "aws_narrow_write": {"enabled": True},
            "aws_csm_onboarding": {"enabled": True},
            "aws_csm_sandbox": {"enabled": False},
        },
        known_tool_ids=["aws", "aws_csm_newsletter", "aws_narrow_write", "aws_csm_onboarding", "aws_csm_sandbox", "maps"],
    )


def _write_private_newsletter_state(root: Path) -> tuple[Path, Path]:
    private_dir = root / "private"
    aws_root = private_dir / "utilities" / "tools" / "aws-csm"
    legacy_root = private_dir / "utilities" / "tools" / "newsletter-admin"
    aws_root.mkdir(parents=True)
    legacy_root.mkdir(parents=True)
    status_file = root / "aws-csm.fnd.dylan.json"
    profile_payload = {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.fnd.dylan",
            "tenant_id": "fnd",
            "domain": "fruitfulnetworkdevelopment.com",
            "mailbox_local_part": "dylan",
            "role": "operator",
            "send_as_email": "dylan@fruitfulnetworkdevelopment.com",
        },
        "smtp": {"handoff_ready": True, "credentials_secret_state": "configured"},
        "verification": {"status": "verified"},
        "provider": {"gmail_send_as_status": "verified"},
        "workflow": {"initiated": True, "lifecycle_state": "operational", "is_mailbox_operational": True},
        "inbound": {"receive_verified": True, "receive_state": "receive_operational"},
    }
    status_file.write_text(json.dumps(profile_payload) + "\n", encoding="utf-8")
    (aws_root / "aws-csm.fnd.dylan.json").write_text(json.dumps(profile_payload) + "\n", encoding="utf-8")
    (legacy_root / "newsletter-admin.fruitfulnetworkdevelopment.com.json").write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.newsletter.profile.v1",
                "domain": "fruitfulnetworkdevelopment.com",
                "list_address": "news@fruitfulnetworkdevelopment.com",
                "sender_address": "news@fruitfulnetworkdevelopment.com",
                "selected_author_profile_id": "aws-csm.fnd.dylan",
                "selected_author_address": "dylan@fruitfulnetworkdevelopment.com",
                "dispatch_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/aws-cms-newsletter-dispatch",
                "dispatch_queue_arn": "arn:aws:sqs:us-east-1:123456789012:aws-cms-newsletter-dispatch",
                "dispatcher_lambda_name": "newsletter-dispatcher",
                "aws_region": "us-east-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (aws_root / "aws-csm.cvcc.technicalContact.json").write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.aws_csm.profile.v1",
                "identity": {
                    "profile_id": "aws-csm.cvcc.technicalContact",
                    "tenant_id": "fnd",
                    "domain": "cuyahogavalleycountrysideconservancy.org",
                    "mailbox_local_part": "technicalContact",
                    "role": "technical_contact",
                    "send_as_email": "technicalcontact@cuyahogavalleycountrysideconservancy.org",
                },
                "smtp": {"handoff_ready": True, "credentials_secret_state": "configured"},
                "verification": {"status": "verified"},
                "provider": {"gmail_send_as_status": "verified"},
                "workflow": {"initiated": True, "lifecycle_state": "operational", "is_mailbox_operational": True},
                "inbound": {"receive_verified": True, "receive_state": "receive_operational"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (legacy_root / "newsletter-admin.cuyahogavalleycountrysideconservancy.org.json").write_text(
        json.dumps(
            {
                "schema": "mycite.service_tool.newsletter.profile.v1",
                "domain": "cuyahogavalleycountrysideconservancy.org",
                "list_address": "news@cuyahogavalleycountrysideconservancy.org",
                "sender_address": "news@cuyahogavalleycountrysideconservancy.org",
                "selected_author_profile_id": "aws-csm.cvcc.technicalContact",
                "selected_author_address": "technicalcontact@cuyahogavalleycountrysideconservancy.org",
                "dispatch_queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/aws-cms-newsletter-dispatch",
                "dispatch_queue_arn": "arn:aws:sqs:us-east-1:123456789012:aws-cms-newsletter-dispatch",
                "dispatcher_lambda_name": "newsletter-dispatcher",
                "aws_region": "us-east-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return private_dir, status_file


class AdminAwsCsmFamilyRuntimeIntegrationTests(unittest.TestCase):
    @patch("MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud.AwsEc2RoleNewsletterCloudAdapter.receipt_rule_summary")
    @patch("MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud.AwsEc2RoleNewsletterCloudAdapter.lambda_health_summary")
    @patch("MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud.AwsEc2RoleNewsletterCloudAdapter.queue_health_summary")
    @patch("MyCiteV2.packages.adapters.event_transport.aws_csm_newsletter_cloud.AwsEc2RoleNewsletterCloudAdapter.caller_identity_summary")
    def test_family_home_returns_domain_summary_and_navigation(
        self,
        caller_identity_summary,
        queue_health_summary,
        lambda_health_summary,
        receipt_rule_summary,
    ) -> None:
        caller_identity_summary.return_value = {"status": "ok", "arn": "arn:aws:sts::123456789012:assumed-role/EC2-AWSCMS-Admin/test"}
        queue_health_summary.return_value = {"status": "ok", "queue_arn": "arn:aws:sqs:us-east-1:123456789012:aws-cms-newsletter-dispatch"}
        lambda_health_summary.return_value = {"status": "active", "function_arn": "arn:aws:lambda:us-east-1:123456789012:function:newsletter-dispatcher"}
        receipt_rule_summary.return_value = {"status": "ok", "matching_rules": [{"rule_name": "capture-fnd"}]}
        with TemporaryDirectory() as temp_dir:
            private_dir, status_file = _write_private_newsletter_state(Path(temp_dir))

            result = run_admin_aws_csm_family_home(
                {
                    "schema": ADMIN_AWS_CSM_FAMILY_HOME_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "fnd", "audience": "trusted-tenant"},
                },
                aws_status_file=status_file,
                private_dir=private_dir,
                tool_exposure_policy=_tool_exposure_policy(newsletter_enabled=True),
            )

            self.assertIsNone(result["error"])
            surface = result["surface_payload"]
            self.assertEqual(surface["schema"], "mycite.v2.admin.aws_csm.family_home.surface.v1")
            self.assertEqual(surface["primary_read_only"]["selected_verified_sender"], "dylan@fruitfulnetworkdevelopment.com")
            self.assertTrue(surface["newsletter_enabled"])
            self.assertEqual(surface["selected_domain_state"]["domain"], "fruitfulnetworkdevelopment.com")
            self.assertEqual(surface["selected_domain_state"]["selected_author"]["profile_id"], "aws-csm.fnd.dylan")
            self.assertEqual(surface["subsurface_navigation"]["newsletter_route"], "/portal/api/v2/admin/aws/newsletter")

    def test_newsletter_subsurface_is_config_gated(self) -> None:
        with TemporaryDirectory() as temp_dir:
            private_dir, _status_file = _write_private_newsletter_state(Path(temp_dir))

            result = run_admin_aws_csm_newsletter(
                {
                    "schema": ADMIN_AWS_CSM_NEWSLETTER_REQUEST_SCHEMA,
                    "tenant_scope": {"scope_id": "fnd", "audience": "trusted-tenant"},
                    "domain": "fruitfulnetworkdevelopment.com",
                    "action": "inspect",
                },
                private_dir=private_dir,
                tool_exposure_policy=_tool_exposure_policy(newsletter_enabled=False),
            )

            self.assertEqual(result["error"]["code"], ADMIN_TOOL_NOT_EXPOSED_ERROR_CODE)
            self.assertIsNone(result["surface_payload"])


if __name__ == "__main__":
    unittest.main()
