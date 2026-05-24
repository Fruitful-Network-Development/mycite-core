"""B2 — email-extension overlay: per-step AWS evidence on the onboarding
progress payload.

Pins:
  * Default (no aws_adapter) — no aws_evidence keys, no probe calls,
    progress is flag-only (preserves the pre-B2 behavior).
  * With a stub adapter — aws_evidence carries entries for the 3
    probed steps (ses_identity_ready, handoff_acked, inbound_verified).
  * auto_advance evidence advances the percent + completed list +
    next_step calculation.
  * drift evidence does NOT change the flag-based percent.
  * MYCITE_DISABLE_EMAIL_OVERLAY_PROBES=1 disables the lazy-create path
    so _render_ext_aws_email is no-op for probes.
  * Cache: repeat _onboarding_progress() calls within TTL don't re-probe.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _profile_payload(
    *,
    ses_status: str = "",        # provider.aws_ses_identity_status
    lifecycle: str = "",         # workflow.lifecycle_state
    handoff_sent: bool = False,
    receive_state: str = "",     # inbound.receive_state
    receive_verified: bool = False,
    initiated: bool = True,
) -> dict[str, Any]:
    workflow: dict[str, Any] = {"lifecycle_state": lifecycle}
    if initiated:
        workflow["initiated"] = True
    if handoff_sent:
        workflow["handoff_email_sent_at"] = "2026-05-22T10:00:00+00:00"
    return {
        "identity": {
            "profile_id": "aws-csm.alpha.support",
            "domain": "alpha.example.test",
            "send_as_email": "support@alpha.example.test",
        },
        "workflow": workflow,
        "provider": {"aws_ses_identity_status": ses_status},
        "inbound": {
            "receive_state": receive_state,
            "receive_verified": receive_verified,
        },
    }


def _evidence(state: str, detail: str = "stub") -> dict[str, str]:
    return {"state": state, "detail": detail, "observed_at": "2026-05-23T12:00:00+00:00"}


def _adapter_returning(
    *, ses_state: str, sends_state: str, inbound_state: str
) -> MagicMock:
    adapter = MagicMock()
    adapter.probe_ses_identity_aws_evidence.return_value = _evidence(ses_state, "ses-stub")
    adapter.probe_operator_sends_aws_evidence.return_value = _evidence(sends_state, "sends-stub")
    adapter.probe_inbound_verified_aws_evidence.return_value = _evidence(inbound_state, "inbound-stub")
    return adapter


class OnboardingProgressFlagOnlyTests(unittest.TestCase):
    """Default (no aws_adapter) — pre-B2 behavior preserved."""

    def setUp(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import email
        self.email = email
        email._OVERLAY_PROBE_CACHE.clear()

    def test_no_adapter_omits_probes_and_aws_evidence_empty(self) -> None:
        payload = _profile_payload(initiated=True, handoff_sent=True)
        result = self.email._onboarding_progress(payload)
        self.assertEqual(result["aws_evidence"], {})
        # Flag-only: profile_created (initiated=True) + handoff_sent → 2 of 6
        self.assertEqual(result["steps_done"], 2)
        self.assertEqual(result["completed"], ["profile_created", "handoff_sent"])

    def test_no_adapter_does_not_call_anything(self) -> None:
        with patch.object(self.email, "_lazy_overlay_adapter") as lazy:
            self.email._onboarding_progress(_profile_payload(initiated=True))
            lazy.assert_not_called()


class OnboardingProgressWithAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import email
        self.email = email
        email._OVERLAY_PROBE_CACHE.clear()

    def test_aws_evidence_keyed_by_step(self) -> None:
        adapter = _adapter_returning(
            ses_state="confirmed", sends_state="absent", inbound_state="drift"
        )
        result = self.email._onboarding_progress(
            _profile_payload(ses_status="verified"), aws_adapter=adapter
        )
        evidence = result["aws_evidence"]
        self.assertIn("ses_identity_ready", evidence)
        self.assertIn("handoff_acked", evidence)
        self.assertIn("inbound_verified", evidence)
        self.assertEqual(evidence["ses_identity_ready"]["state"], "confirmed")
        self.assertEqual(evidence["handoff_acked"]["state"], "absent")
        self.assertEqual(evidence["inbound_verified"]["state"], "drift")

    def test_auto_advance_evidence_advances_percent(self) -> None:
        # Flag-only this would be steps_done=1 (only profile_created).
        # With auto_advance on ses_identity_ready (AWS says verified)
        # the step counts as done.
        adapter = _adapter_returning(
            ses_state="auto_advance", sends_state="absent", inbound_state="absent"
        )
        result = self.email._onboarding_progress(
            _profile_payload(initiated=True),
            aws_adapter=adapter,
        )
        # profile_created + (auto_advance) ses_identity_ready = 2 of 6
        self.assertIn("ses_identity_ready", result["completed"])
        self.assertEqual(result["steps_done"], 2)
        # next_step shifts to the first incomplete one (handoff_sent)
        self.assertEqual(result["next_step"]["key"], "handoff_sent")

    def test_handoff_acked_evidence_is_display_only_not_auto_advance(self) -> None:
        # The operator-sends probe maps to handoff_acked but is an indirect
        # proxy — even when it returns auto_advance, the step must NOT flip
        # complete (only the lifecycle flag does that). Evidence is still
        # attached for the badge.
        adapter = _adapter_returning(
            ses_state="absent", sends_state="auto_advance", inbound_state="absent"
        )
        result = self.email._onboarding_progress(
            _profile_payload(initiated=True),  # lifecycle NOT operational
            aws_adapter=adapter,
        )
        self.assertEqual(result["aws_evidence"]["handoff_acked"]["state"], "auto_advance")
        self.assertNotIn("handoff_acked", result["completed"])
        # Only profile_created is done — handoff_acked did NOT inflate it.
        self.assertEqual(result["steps_done"], 1)

    def test_drift_does_not_change_percent(self) -> None:
        # Flag says ses_identity_ready (provider=verified) so it counts
        # as done; AWS evidence is "drift" (declared but AWS says no).
        # The percent is the flag's truth — drift is the warning signal
        # for the UI but doesn't move the bar backward.
        adapter = _adapter_returning(
            ses_state="drift", sends_state="absent", inbound_state="absent"
        )
        result = self.email._onboarding_progress(
            _profile_payload(initiated=True, ses_status="verified"),
            aws_adapter=adapter,
        )
        self.assertIn("ses_identity_ready", result["completed"])
        self.assertEqual(result["aws_evidence"]["ses_identity_ready"]["state"], "drift")

    def test_probe_results_cached(self) -> None:
        adapter = _adapter_returning(
            ses_state="confirmed", sends_state="absent", inbound_state="absent"
        )
        # First call — probes run.
        self.email._onboarding_progress(
            _profile_payload(initiated=True, ses_status="verified"),
            aws_adapter=adapter,
        )
        # Second call — same payload → same cache key → no new probe.
        self.email._onboarding_progress(
            _profile_payload(initiated=True, ses_status="verified"),
            aws_adapter=adapter,
        )
        self.assertEqual(
            adapter.probe_ses_identity_aws_evidence.call_count, 1
        )
        self.assertEqual(
            adapter.probe_operator_sends_aws_evidence.call_count, 1
        )
        self.assertEqual(
            adapter.probe_inbound_verified_aws_evidence.call_count, 1
        )

    def test_passed_probe_deadline_skips_probes(self) -> None:
        # A deadline already in the past → no probes issued for this
        # mailbox (renders flag-only), so the extension can't blow its
        # 5s render future on a cold multi-mailbox grantee.
        import time as _t
        adapter = _adapter_returning(
            ses_state="confirmed", sends_state="absent", inbound_state="confirmed"
        )
        result = self.email._onboarding_progress(
            _profile_payload(initiated=True, ses_status="verified"),
            aws_adapter=adapter,
            probe_deadline=_t.monotonic() - 1.0,  # already elapsed
        )
        self.assertEqual(result["aws_evidence"], {})
        adapter.probe_ses_identity_aws_evidence.assert_not_called()
        adapter.probe_operator_sends_aws_evidence.assert_not_called()
        adapter.probe_inbound_verified_aws_evidence.assert_not_called()
        # Flag-only progress still computed (profile_created + ses verified).
        self.assertIn("profile_created", result["completed"])

    def test_future_probe_deadline_allows_probes(self) -> None:
        import time as _t
        adapter = _adapter_returning(
            ses_state="confirmed", sends_state="absent", inbound_state="confirmed"
        )
        result = self.email._onboarding_progress(
            _profile_payload(initiated=True, ses_status="verified"),
            aws_adapter=adapter,
            probe_deadline=_t.monotonic() + 30.0,  # plenty of budget
        )
        self.assertIn("ses_identity_ready", result["aws_evidence"])
        adapter.probe_ses_identity_aws_evidence.assert_called_once()


class RenderExtAwsEmailAdapterResolutionTests(unittest.TestCase):
    """_render_ext_aws_email lazy-creates the adapter unless the kill-
    switch env var is set, or ctx explicitly passes aws_adapter=None.
    """

    def setUp(self) -> None:
        from MyCiteV2.instances._shared.runtime.utilities_extensions import email
        self.email = email
        email._OVERLAY_PROBE_CACHE.clear()
        # Reset the lazy-cached adapter
        email._LAZY_OVERLAY_ADAPTER = None

    def test_ctx_explicit_none_skips_probes(self) -> None:
        with patch.object(self.email, "_lazy_overlay_adapter") as lazy:
            adapter = self.email._resolve_overlay_adapter({"aws_adapter": None})
            self.assertIsNone(adapter)
            lazy.assert_not_called()

    def test_ctx_explicit_adapter_used(self) -> None:
        fake = MagicMock()
        adapter = self.email._resolve_overlay_adapter({"aws_adapter": fake})
        self.assertIs(adapter, fake)

    def test_no_ctx_key_lazy_creates_adapter(self) -> None:
        with patch.object(self.email, "_lazy_overlay_adapter") as lazy:
            lazy.return_value = MagicMock(name="lazy-adapter")
            adapter = self.email._resolve_overlay_adapter({})
            lazy.assert_called_once()
            self.assertIs(adapter, lazy.return_value)

    def test_disable_env_var_skips_lazy_create(self) -> None:
        with patch.dict("os.environ", {"MYCITE_DISABLE_EMAIL_OVERLAY_PROBES": "1"}):
            with patch.object(self.email, "_lazy_overlay_adapter") as lazy:
                adapter = self.email._resolve_overlay_adapter({})
                self.assertIsNone(adapter)
                lazy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
