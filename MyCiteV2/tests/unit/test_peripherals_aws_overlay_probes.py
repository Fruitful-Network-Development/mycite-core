"""B1 — activity-based onboarding-overlay probes (3 methods on
AwsPeripheralCloudAdapter).

Pins:
  * probe_ses_identity_aws_evidence — confirmed / auto_advance / drift /
    absent / error states across (live SES verdict × declared_verified flag).
  * probe_operator_sends_aws_evidence — same 5 states across (CloudWatch
    Send count × declared_operational flag); empty send_as → error.
  * probe_inbound_verified_aws_evidence — same 5 states across (S3
    KeyCount × declared_verified flag); invalid domain → error.
  * Each probe captures observed_at as an ISO timestamp.
  * Per-call AWS exceptions yield state=error with detail carrying the
    exception message (so the UI badge surfaces "no data" without
    crashing the render).
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.peripherals.aws.cloud_adapter import AwsPeripheralCloudAdapter


def _adapter_with_stubbed_clients(**stubs):
    """Build an adapter with pre-seeded _client cache so AWS calls use the
    provided stubs instead of touching the network. Keys match the
    `<service>@<region>` shape _client() uses."""
    adapter = AwsPeripheralCloudAdapter(profile_store=MagicMock())
    for service, stub in stubs.items():
        adapter._cached_clients[f"{service}@us-east-1"] = stub
    return adapter


def _assert_iso_utc(self, ts: str) -> None:
    # observed_at must round-trip through fromisoformat as a tz-aware datetime.
    parsed = datetime.fromisoformat(ts)
    self.assertIsNotNone(parsed.tzinfo, f"observed_at {ts!r} not tz-aware")


class ProbeSesIdentityTests(unittest.TestCase):
    def _ses_stub(self, status: str) -> MagicMock:
        stub = MagicMock()
        stub.get_identity_verification_attributes.return_value = {
            "VerificationAttributes": {
                "dylan@example.test": {"VerificationStatus": status}
            }
        }
        return stub

    def test_confirmed_when_aws_success_and_flag_true(self) -> None:
        adapter = _adapter_with_stubbed_clients(ses=self._ses_stub("Success"))
        result = adapter.probe_ses_identity_aws_evidence(
            "dylan@example.test", declared_verified=True
        )
        self.assertEqual(result["state"], "confirmed")
        self.assertIn("Success", result["detail"])
        _assert_iso_utc(self, result["observed_at"])

    def test_auto_advance_when_aws_success_but_flag_false(self) -> None:
        adapter = _adapter_with_stubbed_clients(ses=self._ses_stub("Success"))
        result = adapter.probe_ses_identity_aws_evidence(
            "dylan@example.test", declared_verified=False
        )
        self.assertEqual(result["state"], "auto_advance")

    def test_drift_when_flag_true_but_aws_pending(self) -> None:
        adapter = _adapter_with_stubbed_clients(ses=self._ses_stub("Pending"))
        result = adapter.probe_ses_identity_aws_evidence(
            "dylan@example.test", declared_verified=True
        )
        self.assertEqual(result["state"], "drift")
        self.assertIn("Pending", result["detail"])

    def test_absent_when_neither_side_has_evidence(self) -> None:
        adapter = _adapter_with_stubbed_clients(ses=self._ses_stub(""))
        result = adapter.probe_ses_identity_aws_evidence(
            "dylan@example.test", declared_verified=False
        )
        self.assertEqual(result["state"], "absent")

    def test_aws_exception_yields_state_error(self) -> None:
        ses = MagicMock()
        ses.get_identity_verification_attributes.side_effect = RuntimeError("403 throttle")
        adapter = _adapter_with_stubbed_clients(ses=ses)
        result = adapter.probe_ses_identity_aws_evidence(
            "dylan@example.test", declared_verified=True
        )
        self.assertEqual(result["state"], "error")
        self.assertIn("403 throttle", result["detail"])

    def test_empty_send_as_yields_state_error(self) -> None:
        adapter = _adapter_with_stubbed_clients(ses=MagicMock())
        result = adapter.probe_ses_identity_aws_evidence("", declared_verified=False)
        self.assertEqual(result["state"], "error")
        self.assertIn("empty", result["detail"])


class ProbeOperatorSendsTests(unittest.TestCase):
    def _cw_stub(self, datapoints: list[dict]) -> MagicMock:
        stub = MagicMock()
        stub.get_metric_statistics.return_value = {"Datapoints": datapoints}
        return stub

    def test_confirmed_when_sends_exist_and_lifecycle_operational(self) -> None:
        adapter = _adapter_with_stubbed_clients(
            cloudwatch=self._cw_stub([{"Sum": 5.0}, {"Sum": 2.0}])
        )
        result = adapter.probe_operator_sends_aws_evidence(
            "dylan@example.test", declared_operational=True
        )
        self.assertEqual(result["state"], "confirmed")
        self.assertIn("7 sends", result["detail"])

    def test_auto_advance_when_sends_exist_but_lifecycle_not_operational(self) -> None:
        adapter = _adapter_with_stubbed_clients(
            cloudwatch=self._cw_stub([{"Sum": 3.0}])
        )
        result = adapter.probe_operator_sends_aws_evidence(
            "dylan@example.test", declared_operational=False
        )
        self.assertEqual(result["state"], "auto_advance")
        self.assertIn("3 sends", result["detail"])

    def test_drift_when_lifecycle_operational_but_no_sends(self) -> None:
        adapter = _adapter_with_stubbed_clients(cloudwatch=self._cw_stub([]))
        result = adapter.probe_operator_sends_aws_evidence(
            "dylan@example.test", declared_operational=True
        )
        self.assertEqual(result["state"], "drift")

    def test_absent_when_no_sends_and_lifecycle_not_operational(self) -> None:
        adapter = _adapter_with_stubbed_clients(cloudwatch=self._cw_stub([]))
        result = adapter.probe_operator_sends_aws_evidence(
            "dylan@example.test", declared_operational=False
        )
        self.assertEqual(result["state"], "absent")

    def test_cloudwatch_403_yields_state_error(self) -> None:
        cw = MagicMock()
        cw.get_metric_statistics.side_effect = RuntimeError(
            "AccessDenied: cloudwatch:GetMetricStatistics"
        )
        adapter = _adapter_with_stubbed_clients(cloudwatch=cw)
        result = adapter.probe_operator_sends_aws_evidence("dylan@example.test")
        self.assertEqual(result["state"], "error")
        self.assertIn("AccessDenied", result["detail"])

    def test_empty_send_as_yields_state_error(self) -> None:
        adapter = _adapter_with_stubbed_clients(cloudwatch=MagicMock())
        result = adapter.probe_operator_sends_aws_evidence("")
        self.assertEqual(result["state"], "error")


class ProbeInboundVerifiedTests(unittest.TestCase):
    def _s3_stub(self, key_count: int) -> MagicMock:
        stub = MagicMock()
        stub.list_objects_v2.return_value = {"KeyCount": key_count}
        return stub

    def test_confirmed_when_inbound_exists_and_flag_set(self) -> None:
        adapter = _adapter_with_stubbed_clients(s3=self._s3_stub(1))
        result = adapter.probe_inbound_verified_aws_evidence(
            "example.test", declared_verified=True
        )
        self.assertEqual(result["state"], "confirmed")
        self.assertIn("ses-inbound-fnd-mail", result["detail"])

    def test_auto_advance_when_inbound_exists_but_flag_unset(self) -> None:
        adapter = _adapter_with_stubbed_clients(s3=self._s3_stub(1))
        result = adapter.probe_inbound_verified_aws_evidence(
            "example.test", declared_verified=False
        )
        self.assertEqual(result["state"], "auto_advance")

    def test_drift_when_flag_set_but_no_inbound(self) -> None:
        adapter = _adapter_with_stubbed_clients(s3=self._s3_stub(0))
        result = adapter.probe_inbound_verified_aws_evidence(
            "example.test", declared_verified=True
        )
        self.assertEqual(result["state"], "drift")

    def test_absent_when_no_inbound_and_flag_unset(self) -> None:
        adapter = _adapter_with_stubbed_clients(s3=self._s3_stub(0))
        result = adapter.probe_inbound_verified_aws_evidence(
            "example.test", declared_verified=False
        )
        self.assertEqual(result["state"], "absent")

    def test_s3_exception_yields_state_error(self) -> None:
        s3 = MagicMock()
        s3.list_objects_v2.side_effect = RuntimeError("NoSuchBucket")
        adapter = _adapter_with_stubbed_clients(s3=s3)
        result = adapter.probe_inbound_verified_aws_evidence("example.test")
        self.assertEqual(result["state"], "error")
        self.assertIn("NoSuchBucket", result["detail"])

    def test_empty_domain_yields_state_error(self) -> None:
        adapter = _adapter_with_stubbed_clients(s3=MagicMock())
        result = adapter.probe_inbound_verified_aws_evidence("")
        self.assertEqual(result["state"], "error")
        self.assertIn("invalid_domain", result["detail"])

    def test_custom_bucket_and_prefix_template(self) -> None:
        s3 = self._s3_stub(2)
        adapter = _adapter_with_stubbed_clients(s3=s3)
        adapter.probe_inbound_verified_aws_evidence(
            "example.test",
            declared_verified=True,
            bucket="alt-bucket",
            prefix_template="capture/{domain}/raw/",
        )
        # The boto3 list_objects_v2 should have been called with the
        # interpolated bucket + prefix.
        s3.list_objects_v2.assert_called_once()
        kwargs = s3.list_objects_v2.call_args.kwargs
        self.assertEqual(kwargs["Bucket"], "alt-bucket")
        self.assertEqual(kwargs["Prefix"], "capture/example.test/raw/")


if __name__ == "__main__":
    unittest.main()
