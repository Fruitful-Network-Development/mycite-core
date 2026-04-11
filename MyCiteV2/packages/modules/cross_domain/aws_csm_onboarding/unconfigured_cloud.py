"""Default cloud port: no external IO; ``confirm_verified`` stays fail-closed."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.ports.aws_csm_onboarding import AwsCsmOnboardingCloudPort


class AwsCsmOnboardingUnconfiguredCloudPort:
    """Production default until SES/S3/Route53 adapters are wired."""

    def supplemental_profile_patch(self, action: str, profile: dict[str, Any]) -> dict[str, Any]:
        _ = action, profile
        return {}

    def gmail_confirmation_evidence_satisfied(self, profile: dict[str, Any]) -> bool:
        _ = profile
        return False


__all__ = ["AwsCsmOnboardingUnconfiguredCloudPort"]
