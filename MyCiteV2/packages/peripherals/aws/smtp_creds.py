"""SES SMTP credential derivation.

When you "create SMTP credentials" in the SES console it actually creates
an IAM user and access key under the hood, then displays the IAM secret
transformed into an SMTP password via a documented HMAC-SHA256 derivation.
Same algorithm here so we can mint per-user Send-As credentials from a
scripted onboard-user flow without round-tripping through the console.

Reference: AWS SES Developer Guide — "Converting Existing AWS Credentials
into SES SMTP Credentials" (algorithm version 4, region-aware).
"""
from __future__ import annotations

import base64
import hashlib
import hmac

# Version byte the SES SMTP server expects as the first byte of the
# decoded password. v4 is the current (region-aware) format.
SES_SMTP_PASSWORD_VERSION = 0x04


def derive_smtp_password(secret_access_key: str, region: str) -> str:
    """Return the SES SMTP password for ``secret_access_key`` in ``region``.

    The SMTP username is the IAM access key id (unchanged); the SMTP
    password is HMAC-SHA256-derived from the secret access key as below,
    then base64-encoded with the v4 version byte prefixed.

        signing_key = HMAC-SHA256("AWS4" + secret_access_key, "11111111")
        signing_key = HMAC-SHA256(signing_key, region)
        signing_key = HMAC-SHA256(signing_key, "ses")
        signing_key = HMAC-SHA256(signing_key, "aws4_request")
        signature   = HMAC-SHA256(signing_key, "SendRawEmail")
        password    = base64(bytes([0x04]) + signature)

    Both inputs are required. The function does no I/O.
    """
    if not isinstance(secret_access_key, str) or not secret_access_key:
        raise ValueError("secret_access_key must be a non-empty string")
    if not isinstance(region, str) or not region:
        raise ValueError("region must be a non-empty string")

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    signing_key = _sign(("AWS4" + secret_access_key).encode("utf-8"), "11111111")
    signing_key = _sign(signing_key, region)
    signing_key = _sign(signing_key, "ses")
    signing_key = _sign(signing_key, "aws4_request")
    signature = _sign(signing_key, "SendRawEmail")

    return base64.b64encode(bytes([SES_SMTP_PASSWORD_VERSION]) + signature).decode("ascii")


def smtp_host_for_region(region: str) -> str:
    """Return the SES SMTP endpoint hostname for ``region``."""
    region = (region or "").strip()
    if not region:
        raise ValueError("region must be a non-empty string")
    return f"email-smtp.{region}.amazonaws.com"


def scoped_send_policy_document(from_address: str) -> dict:
    """Return an IAM policy document that allows ``ses:SendRawEmail`` only
    when the message's From: address matches ``from_address``.

    This is the policy attached to each per-user SMTP IAM user. Credential
    leak blast radius = ability to send AS this one address; cannot
    impersonate other identities even on the same SES account.
    """
    if not from_address or "@" not in from_address:
        raise ValueError("from_address must be a non-empty email address")
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowSendOnlyAsThisAddress",
                "Effect": "Allow",
                "Action": ["ses:SendRawEmail", "ses:SendEmail"],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "ses:FromAddress": from_address,
                    },
                },
            },
        ],
    }


def slugify_iam_user_name(address: str) -> str:
    """Return the IAM user name used for the SMTP credentials backing
    ``address``.

    Form: ``ses-smtp-<domain-with-dots-as-hyphens>-<local>``. Stable across
    runs so re-running ``onboard-user`` is idempotent (we either find the
    existing user or know to skip creation).
    """
    if "@" not in address:
        raise ValueError("address must be an email address")
    local, domain = address.split("@", 1)
    safe_local = local.strip().lower().replace(".", "-")
    safe_domain = domain.strip().lower().replace(".", "-")
    return f"ses-smtp-{safe_domain}-{safe_local}"
