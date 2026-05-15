from __future__ import annotations

import os
import sys
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from MyCiteV2.packages.adapters.event_transport.aws_csm_onboarding_cloud import (
    AWS_CSM_HANDOFF_CONFIGURATION_SET_ENV,
    AWS_CSM_HANDOFF_FROM_EMAIL_ENV,
    AWS_CSM_HANDOFF_REPLY_TO_ENV,
    AWS_CSM_HANDOFF_TEMPLATE_VERSION,
    AwsEc2RoleOnboardingCloudAdapter,
)

_DEFAULT_FROM = "dylan@fruitfulnetworkdevelopment.com"
_SEND_AS = "mark@trappfamilyfarm.com"
_DESTINATION = "trapp.family.farm@gmail.com"
_SMTP_HOST = "email-smtp.us-east-1.amazonaws.com"
_SMTP_PORT = "587"
_USERNAME = "AKIAEXAMPLEACCESSKEY"
_PASSWORD = "BTw3xampleSesSmtpPassword/With+Special&Chars<>\""


class _FakeSesV2:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_email(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"MessageId": "ses-unit-001"}


def _make_profile() -> dict[str, Any]:
    return {
        "identity": {
            "profile_id": "aws-csm.tff.mark",
            "tenant_id": "tff",
            "domain": "trappfamilyfarm.com",
            "region": "us-east-1",
            "send_as_email": _SEND_AS,
            "operator_inbox_target": _DESTINATION,
        },
        "smtp": {
            "host": _SMTP_HOST,
            "port": _SMTP_PORT,
            "forward_to_email": _DESTINATION,
            "send_as_email": _SEND_AS,
        },
        "workflow": {"handoff_provider": "gmail"},
    }


def _make_adapter() -> tuple[AwsEc2RoleOnboardingCloudAdapter, _FakeSesV2]:
    adapter = AwsEc2RoleOnboardingCloudAdapter()
    fake = _FakeSesV2()

    def fake_client(service_name: str, region: str | None = None) -> Any:
        if service_name != "sesv2":
            raise AssertionError(f"unexpected boto3 service requested: {service_name}")
        return fake

    adapter._client = fake_client  # type: ignore[assignment]
    adapter.read_handoff_secret = lambda profile: {  # type: ignore[assignment]
        "username": _USERNAME,
        "password": _PASSWORD,
        "smtp_host": _SMTP_HOST,
        "smtp_port": _SMTP_PORT,
        "state": "configured",
    }
    return adapter, fake


class _ResetEnv:
    """Test helper that snapshots and restores the three handoff env vars."""

    _KEYS = (
        AWS_CSM_HANDOFF_FROM_EMAIL_ENV,
        AWS_CSM_HANDOFF_REPLY_TO_ENV,
        AWS_CSM_HANDOFF_CONFIGURATION_SET_ENV,
    )

    def __enter__(self) -> _ResetEnv:
        self._prior = {k: os.environ.get(k) for k in self._KEYS}
        for k in self._KEYS:
            os.environ.pop(k, None)
        return self

    def set(self, key: str, value: str) -> None:
        os.environ[key] = value

    def __exit__(self, *exc: Any) -> None:
        for k, v in self._prior.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class HandoffEmailSendTests(unittest.TestCase):
    def test_default_from_when_env_unset(self) -> None:
        with _ResetEnv():
            adapter, fake = _make_adapter()
            result = adapter.send_handoff_email(_make_profile())

        self.assertEqual(len(fake.calls), 1)
        kwargs = fake.calls[0]
        self.assertEqual(kwargs["FromEmailAddress"], _DEFAULT_FROM)
        self.assertEqual(kwargs["ReplyToAddresses"], [_DEFAULT_FROM])
        self.assertEqual(kwargs["Destination"], {"ToAddresses": [_DESTINATION]})
        self.assertNotIn("ConfigurationSetName", kwargs)
        self.assertEqual(result["from_email"], _DEFAULT_FROM)
        self.assertEqual(result["reply_to"], _DEFAULT_FROM)
        self.assertEqual(result["configuration_set"], "")
        self.assertEqual(result["sent_to"], _DESTINATION)
        self.assertEqual(result["send_as_email"], _SEND_AS)
        self.assertEqual(result["template_version"], AWS_CSM_HANDOFF_TEMPLATE_VERSION)
        self.assertEqual(result["correction"], "false")

    def test_env_override_from_and_reply_to(self) -> None:
        with _ResetEnv() as env:
            env.set(AWS_CSM_HANDOFF_FROM_EMAIL_ENV, "ops@example.org")
            env.set(AWS_CSM_HANDOFF_REPLY_TO_ENV, "support@example.org")
            adapter, fake = _make_adapter()
            adapter.send_handoff_email(_make_profile())
        kwargs = fake.calls[0]
        self.assertEqual(kwargs["FromEmailAddress"], "ops@example.org")
        self.assertEqual(kwargs["ReplyToAddresses"], ["support@example.org"])

    def test_reply_to_defaults_to_from_when_only_from_overridden(self) -> None:
        with _ResetEnv() as env:
            env.set(AWS_CSM_HANDOFF_FROM_EMAIL_ENV, "ops@example.org")
            adapter, fake = _make_adapter()
            adapter.send_handoff_email(_make_profile())
        kwargs = fake.calls[0]
        self.assertEqual(kwargs["FromEmailAddress"], "ops@example.org")
        self.assertEqual(kwargs["ReplyToAddresses"], ["ops@example.org"])

    def test_configuration_set_attached_when_env_set(self) -> None:
        with _ResetEnv() as env:
            env.set(AWS_CSM_HANDOFF_CONFIGURATION_SET_ENV, "aws-csm-handoff")
            adapter, fake = _make_adapter()
            result = adapter.send_handoff_email(_make_profile())
        kwargs = fake.calls[0]
        self.assertEqual(kwargs["ConfigurationSetName"], "aws-csm-handoff")
        self.assertEqual(result["configuration_set"], "aws-csm-handoff")

    def test_template_version_is_bumped(self) -> None:
        self.assertEqual(
            AWS_CSM_HANDOFF_TEMPLATE_VERSION, "smtp_credentials_v3_prose_html_2026_05"
        )
        with _ResetEnv():
            adapter, fake = _make_adapter()
            result = adapter.send_handoff_email(_make_profile())
        self.assertEqual(
            result["template_version"], "smtp_credentials_v3_prose_html_2026_05"
        )
        # ConfigurationSetName must not leak into the kwargs when env unset.
        self.assertNotIn("ConfigurationSetName", fake.calls[0])

    def test_raw_multipart_carries_text_and_html_with_creds(self) -> None:
        with _ResetEnv():
            adapter, fake = _make_adapter()
            adapter.send_handoff_email(_make_profile())
        kwargs = fake.calls[0]
        raw = kwargs["Content"]["Raw"]["Data"]
        self.assertIsInstance(raw, (bytes, bytearray))
        message = BytesParser(policy=policy.default).parsebytes(bytes(raw))
        self.assertTrue(message.is_multipart())
        self.assertEqual(message.get_content_subtype(), "alternative")
        parts = list(message.iter_parts())
        content_types = {p.get_content_type() for p in parts}
        self.assertIn("text/plain", content_types)
        self.assertIn("text/html", content_types)

        plain = next(p for p in parts if p.get_content_type() == "text/plain")
        plain_body = plain.get_content()
        self.assertIn(_SEND_AS, plain_body)
        self.assertIn(_USERNAME, plain_body)
        self.assertIn(_PASSWORD, plain_body)
        self.assertIn(_SMTP_HOST, plain_body)
        self.assertIn("Hi,", plain_body)
        self.assertIn("FND Operations", plain_body)

        html = next(p for p in parts if p.get_content_type() == "text/html")
        html_body = html.get_content()
        self.assertIn(_SEND_AS, html_body)
        self.assertIn(_USERNAME, html_body)
        # Password contains <, >, ", & — these must be HTML-escaped, so we
        # check on the escaped form too.
        import html as _html

        self.assertIn(_html.escape(_PASSWORD), html_body)

    def test_subject_unchanged_by_default(self) -> None:
        with _ResetEnv():
            adapter, fake = _make_adapter()
            adapter.send_handoff_email(_make_profile())
        raw = fake.calls[0]["Content"]["Raw"]["Data"]
        message = BytesParser(policy=policy.default).parsebytes(bytes(raw))
        self.assertEqual(
            message["Subject"], f"AWS-CSM Gmail send-as handoff for {_SEND_AS}"
        )

    def test_correction_email_carries_note_and_correction_subject(self) -> None:
        with _ResetEnv():
            adapter, fake = _make_adapter()
            result = adapter.send_handoff_correction_email(_make_profile())
        kwargs = fake.calls[0]
        raw = kwargs["Content"]["Raw"]["Data"]
        message = BytesParser(policy=policy.default).parsebytes(bytes(raw))
        self.assertEqual(
            message["Subject"], f"AWS-CSM send-as correction for {_SEND_AS}"
        )
        plain = next(
            p for p in message.iter_parts() if p.get_content_type() == "text/plain"
        )
        plain_body = plain.get_content()
        self.assertIn("Correction:", plain_body)
        self.assertEqual(result["correction"], "true")

    def test_message_id_uses_handoff_from_domain(self) -> None:
        with _ResetEnv():
            adapter, fake = _make_adapter()
            adapter.send_handoff_email(_make_profile())
        raw = fake.calls[0]["Content"]["Raw"]["Data"]
        message = BytesParser(policy=policy.default).parsebytes(bytes(raw))
        message_id = message["Message-ID"]
        self.assertTrue(message_id)
        self.assertIn("@fruitfulnetworkdevelopment.com>", message_id)


if __name__ == "__main__":
    unittest.main()
