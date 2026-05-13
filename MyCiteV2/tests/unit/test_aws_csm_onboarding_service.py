"""Service-layer tests for AwsCsmOnboardingService.

Focus: the auto-sync hook for ``sync_operator_forwarding_routes`` that
fires after every onboarding action affecting inbound state.
"""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.modules.cross_domain.aws_csm_onboarding import AwsCsmOnboardingService
from MyCiteV2.packages.modules.cross_domain.aws_csm_onboarding.service import (
    _INBOUND_TOUCHING_ACTIONS,
)


def _profile(profile_id: str = "aws-csm.cvccboard.elizabeth") -> dict[str, object]:
    return {
        "schema": "mycite.service_tool.aws_csm.profile.v1",
        "identity": {
            "profile_id": profile_id,
            "tenant_id": "cvccboard",
            "domain": "cvccboard.org",
            "send_as_email": "elizabeth@cvccboard.org",
            "handoff_provider": "gmail",
        },
        "smtp": {"forward_to_email": "elizabeth.brake@gmail.com"},
        "verification": {"status": "pending"},
        "provider": {"handoff_provider": "gmail"},
        "workflow": {"is_ready_for_user_handoff": True},
        "inbound": {
            "receive_routing_target": "elizabeth.brake@gmail.com",
            "receive_state": "receive_unconfigured",
        },
    }


class _Store:
    def __init__(self, profiles: list[dict[str, object]]) -> None:
        self.profiles = [deepcopy(p) for p in profiles]

    def load_profile(self, *, tenant_scope_id: str, profile_id: str):
        for p in self.profiles:
            if p["identity"]["profile_id"] == profile_id:  # type: ignore[index]
                return deepcopy(p)
        return None

    def save_profile(self, *, tenant_scope_id: str, profile_id: str, payload):
        for i, p in enumerate(self.profiles):
            if p["identity"]["profile_id"] == profile_id:  # type: ignore[index]
                self.profiles[i] = deepcopy(payload)
                return deepcopy(payload)
        self.profiles.append(deepcopy(payload))
        return deepcopy(payload)

    def list_profiles(self, *, tenant_scope_id=None):
        return [deepcopy(p) for p in self.profiles]


class _Cloud:
    def __init__(self, *, sync_result=None, sync_raises: Exception | None = None) -> None:
        self.sync_result = sync_result if sync_result is not None else {"status": "success"}
        self.sync_raises = sync_raises
        self.sync_calls: list[list[dict[str, object]]] = []
        self.patch_calls: list[str] = []

    def supplemental_profile_patch(self, action: str, profile):
        self.patch_calls.append(action)
        return {}

    def confirmation_evidence_satisfied(self, profile):
        return False

    def gmail_confirmation_evidence_satisfied(self, profile):
        return False

    def sync_operator_forwarding_routes(self, *, profiles):
        self.sync_calls.append(list(profiles or []))
        if self.sync_raises is not None:
            raise self.sync_raises
        return self.sync_result


def _command(action: str) -> dict[str, object]:
    return {
        "tenant_scope": {"scope_id": "cvccboard"},
        "focus_subject": "3-2-3-17-77-1-6-4-1-4.4-1-77",
        "profile_id": "aws-csm.cvccboard.elizabeth",
        "onboarding_action": action,
    }


class AutoSyncHookTests(unittest.TestCase):
    def test_inbound_touching_actions_trigger_sync(self):
        for action in _INBOUND_TOUCHING_ACTIONS:
            with self.subTest(action=action):
                store = _Store([_profile()])
                cloud = _Cloud(sync_result={"status": "success", "route_count": 1})
                service = AwsCsmOnboardingService(profile_store=store, cloud=cloud)
                outcome = service.apply(_command(action))
                self.assertEqual(len(cloud.sync_calls), 1, action)
                self.assertEqual(outcome.forwarding_sync, {"status": "success", "route_count": 1})

    def test_non_inbound_action_does_not_trigger_sync(self):
        store = _Store([_profile()])
        cloud = _Cloud()
        service = AwsCsmOnboardingService(profile_store=store, cloud=cloud)
        outcome = service.apply(_command("begin_onboarding"))
        self.assertEqual(cloud.sync_calls, [])
        self.assertIsNone(outcome.forwarding_sync)

    def test_sync_failure_does_not_block_save(self):
        store = _Store([_profile()])
        cloud = _Cloud(sync_raises=RuntimeError("boto3 exploded"))
        service = AwsCsmOnboardingService(profile_store=store, cloud=cloud)
        outcome = service.apply(_command("refresh_inbound_status"))
        # Save still happened: the working profile is the saved profile
        self.assertEqual(outcome.saved_profile["identity"]["profile_id"], "aws-csm.cvccboard.elizabeth")
        # forwarding_sync surfaces the failure
        self.assertEqual(outcome.forwarding_sync, {"status": "failed", "error": "boto3 exploded"})

    def test_sync_receives_all_profiles_not_just_command_target(self):
        # The lambda env is global across tenants; the sync must always
        # operate on the full profile list, not on the command's tenant
        # subset.
        other = _profile(profile_id="aws-csm.tff.mark")
        other["identity"]["tenant_id"] = "tff"  # type: ignore[index]
        other["identity"]["domain"] = "trappfamilyfarm.com"  # type: ignore[index]
        other["identity"]["send_as_email"] = "mark@trappfamilyfarm.com"  # type: ignore[index]
        store = _Store([_profile(), other])
        cloud = _Cloud()
        service = AwsCsmOnboardingService(profile_store=store, cloud=cloud)
        service.apply(_command("refresh_inbound_status"))
        self.assertEqual(len(cloud.sync_calls), 1)
        recipients = sorted(
            p["identity"]["send_as_email"] for p in cloud.sync_calls[0]  # type: ignore[index]
        )
        self.assertEqual(recipients, ["elizabeth@cvccboard.org", "mark@trappfamilyfarm.com"])

    def test_outcome_audit_payload_includes_forwarding_sync(self):
        store = _Store([_profile()])
        cloud = _Cloud(sync_result={"status": "success", "route_count": 5})
        service = AwsCsmOnboardingService(profile_store=store, cloud=cloud)
        outcome = service.apply(_command("refresh_inbound_status"))
        audit = outcome.to_local_audit_payload()
        self.assertIn("forwarding_sync", audit["details"])
        self.assertEqual(audit["details"]["forwarding_sync"]["route_count"], 5)


if __name__ == "__main__":
    unittest.main()
