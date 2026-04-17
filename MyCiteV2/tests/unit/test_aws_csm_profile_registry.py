from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_csm_profile_registry import (
    AwsCsmProfileRegistryService,
)


class _FakeRegistryPort:
    def __init__(self, *, seed: dict[str, object] | None = None, profiles: list[dict[str, object]] | None = None) -> None:
        self.seed = dict(seed or {})
        self.profiles = [deepcopy(item) for item in list(profiles or [])]
        self.created: list[dict[str, object]] = []

    def list_profiles(self) -> list[dict[str, object]]:
        return [deepcopy(item) for item in self.profiles]

    def resolve_domain_seed(self, *, domain: str) -> dict[str, object] | None:
        if domain == self.seed.get("domain"):
            return deepcopy(self.seed)
        return None

    def create_profile(self, *, profile_id: str, payload: dict[str, object]) -> dict[str, object]:
        _ = profile_id
        self.created.append(deepcopy(payload))
        self.profiles.append(deepcopy(payload))
        return deepcopy(payload)


class AwsCsmProfileRegistryServiceTests(unittest.TestCase):
    def test_create_profile_derives_expected_mailbox_fields(self) -> None:
        registry = _FakeRegistryPort(
            seed={
                "domain": "fruitfulnetworkdevelopment.com",
                "tenant_id": "fnd",
                "region": "us-east-1",
                "provider": {"aws_ses_identity_status": "verified", "last_checked_at": "2026-04-17T00:00:00+00:00"},
            }
        )

        outcome = AwsCsmProfileRegistryService(registry).create_profile(
            {
                "domain": "fruitfulnetworkdevelopment.com",
                "mailbox_local_part": "alex",
                "single_user_email": "alex@example.com",
                "operator_inbox_target": "ops@example.com",
            }
        )

        self.assertEqual(outcome.profile_id, "aws-csm.fnd.alex")
        created = outcome.created_profile
        self.assertEqual(created["identity"]["send_as_email"], "alex@fruitfulnetworkdevelopment.com")
        self.assertEqual(created["identity"]["single_user_email"], "alex@example.com")
        self.assertEqual(created["identity"]["operator_inbox_target"], "ops@example.com")
        self.assertEqual(created["smtp"]["forward_to_email"], "ops@example.com")
        self.assertEqual(created["smtp"]["credentials_secret_name"], "aws-cms/smtp/fnd.alex")
        self.assertEqual(created["workflow"]["lifecycle_state"], "draft")
        self.assertEqual(created["workflow"]["handoff_status"], "not_started")
        self.assertEqual(created["verification"]["portal_state"], "not_started")
        self.assertEqual(created["provider"]["gmail_send_as_status"], "not_started")
        self.assertEqual(created["inbound"]["receive_state"], "receive_unconfigured")

    def test_create_profile_rejects_duplicates_for_profile_send_as_and_single_user(self) -> None:
        existing = {
            "schema": "mycite.service_tool.aws_csm.profile.v1",
            "identity": {
                "profile_id": "aws-csm.fnd.alex",
                "tenant_id": "fnd",
                "domain": "fruitfulnetworkdevelopment.com",
                "send_as_email": "alex@fruitfulnetworkdevelopment.com",
                "single_user_email": "alex@example.com",
            },
        }
        registry = _FakeRegistryPort(
            seed={"domain": "fruitfulnetworkdevelopment.com", "tenant_id": "fnd", "region": "us-east-1"},
            profiles=[existing],
        )
        service = AwsCsmProfileRegistryService(registry)

        with self.assertRaisesRegex(ValueError, "profile_id already exists"):
            service.create_profile(
                {
                    "domain": "fruitfulnetworkdevelopment.com",
                    "mailbox_local_part": "alex",
                    "single_user_email": "new@example.com",
                }
            )

        with self.assertRaisesRegex(ValueError, "single_user_email already exists"):
            service.create_profile(
                {
                    "domain": "fruitfulnetworkdevelopment.com",
                    "mailbox_local_part": "jordan",
                    "single_user_email": "alex@example.com",
                }
            )

    def test_create_profile_requires_seed_tenant_metadata(self) -> None:
        service = AwsCsmProfileRegistryService(_FakeRegistryPort())
        with self.assertRaisesRegex(ValueError, "no seed tenant metadata exists"):
            service.create_profile(
                {
                    "domain": "fruitfulnetworkdevelopment.com",
                    "mailbox_local_part": "alex",
                    "single_user_email": "alex@example.com",
                }
            )


if __name__ == "__main__":
    unittest.main()
