from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_csm_onboarding import AwsCsmOnboardingService
from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingPolicyError


def _profile(*, handoff_provider: str = "gmail") -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": "aws-csm.cvcc.admin",
            "tenant_id": "cvcc",
            "domain": "cuyahogavalleycountrysideconservancy.org",
            "send_as_email": "admin@cuyahogavalleycountrysideconservancy.org",
            "handoff_provider": handoff_provider,
        },
        "smtp": {
            "credentials_secret_state": "configured",
            "forward_to_email": "dylancarsonmontgomery@gmail.com",
        },
        "verification": {"status": "pending", "portal_state": "capture_ready", "link": ""},
        "provider": {"handoff_provider": handoff_provider, "send_as_provider_status": "pending"},
        "workflow": {"handoff_status": "ready_for_handoff", "is_ready_for_user_handoff": False},
        "inbound": {"portal_native_display_ready": True},
    }


class _Store:
    def __init__(self, profile: dict[str, object]) -> None:
        self.profile = deepcopy(profile)

    def load_profile(self, *, tenant_scope_id: str, profile_id: str) -> dict[str, object] | None:
        _ = tenant_scope_id, profile_id
        return deepcopy(self.profile)

    def save_profile(self, *, tenant_scope_id: str, profile_id: str, payload: dict[str, object]) -> dict[str, object]:
        _ = tenant_scope_id, profile_id
        self.profile = deepcopy(payload)
        return deepcopy(payload)


class _Cloud:
    def __init__(self, *, evidence: bool) -> None:
        self.evidence = evidence

    def supplemental_profile_patch(self, action: str, profile: dict[str, object]) -> dict[str, object]:
        _ = action, profile
        return {}

    def confirmation_evidence_satisfied(self, profile: dict[str, object]) -> bool:
        _ = profile
        return self.evidence


class AwsCsmOnboardingServiceTests(unittest.TestCase):
    def test_begin_onboarding_records_initiated_timestamp(self) -> None:
        store = _Store(_profile())
        service = AwsCsmOnboardingService(profile_store=store, cloud=_Cloud(evidence=False))
        outcome = service.apply(
            {
                "tenant_scope": {"scope_id": "cvcc"},
                "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                "profile_id": "aws-csm.cvcc.admin",
                "onboarding_action": "begin_onboarding",
            }
        )
        saved = outcome.saved_profile
        self.assertEqual(saved["workflow"]["initiated"], True)
        self.assertTrue(saved["workflow"]["initiated_at"])
        self.assertEqual(outcome.updated_sections, ("workflow",))

    def test_confirm_verified_requires_evidence(self) -> None:
        service = AwsCsmOnboardingService(
            profile_store=_Store(_profile()),
            cloud=_Cloud(evidence=False),
        )
        with self.assertRaises(AwsCsmOnboardingPolicyError):
            service.apply(
                {
                    "tenant_scope": {"scope_id": "cvcc"},
                    "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                    "profile_id": "aws-csm.cvcc.admin",
                    "onboarding_action": "confirm_verified",
                }
            )

    def test_confirm_verified_attested_succeeds_without_evidence(self) -> None:
        store = _Store(_profile(handoff_provider="outlook"))
        service = AwsCsmOnboardingService(profile_store=store, cloud=_Cloud(evidence=False))
        outcome = service.apply(
            {
                "tenant_scope": {"scope_id": "cvcc"},
                "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
                "profile_id": "aws-csm.cvcc.admin",
                "onboarding_action": "confirm_verified_attested",
            }
        )
        saved = outcome.saved_profile
        self.assertEqual(saved["verification"]["status"], "verified")
        self.assertEqual(saved["verification"]["verification_mode"], "attested")
        self.assertEqual(saved["provider"]["handoff_provider"], "outlook")
        self.assertEqual(saved["provider"]["send_as_provider_status"], "verified")
        self.assertEqual(saved["workflow"]["is_ready_for_user_handoff"], True)


if __name__ == "__main__":
    unittest.main()
