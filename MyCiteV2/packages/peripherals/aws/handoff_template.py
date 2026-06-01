"""Operator-mailbox handoff email template.

Plain Python f-strings — no Jinja — so the copy can be edited without
touching boto3 / SES code in the AWS peripheral cloud adapter.

Two public callables and one constant:

- ``HANDOFF_TEMPLATE_VERSION``      stamped into the profile JSON
- ``handoff_subject(profile)``      returns the Subject header
- ``handoff_body(profile, smtp)``   returns the plain-text Body
"""

from __future__ import annotations

from typing import Any

HANDOFF_TEMPLATE_VERSION = "smtp_credentials_v3_resend_2026_05"


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _identity(profile: dict[str, Any]) -> dict[str, Any]:
    raw = profile.get("identity") if isinstance(profile, dict) else None
    return raw if isinstance(raw, dict) else {}


def _smtp_section(profile: dict[str, Any]) -> dict[str, Any]:
    raw = profile.get("smtp") if isinstance(profile, dict) else None
    return raw if isinstance(raw, dict) else {}


def handoff_subject(profile: dict[str, Any]) -> str:
    ident = _identity(profile)
    send_as = _as_text(ident.get("send_as_email"))
    if send_as:
        return f"[Action needed] Finish setting up {send_as}"
    return "[Action needed] Finish setting up your cvccboard.org mailbox"


def handoff_body(profile: dict[str, Any], smtp: dict[str, Any]) -> str:
    """Render the operator-facing handoff message.

    ``smtp`` carries the ephemeral SMTP material returned by
    ``read_handoff_secret`` (host, port, username, password, send_as).
    The password is interpolated once into the rendered body — it is
    NEVER persisted by the caller.
    """
    ident = _identity(profile)
    smtp_meta = _smtp_section(profile)

    send_as = _as_text(ident.get("send_as_email")) or _as_text(
        smtp_meta.get("send_as_email")
    )
    inbox = _as_text(ident.get("operator_inbox_target")) or _as_text(
        smtp_meta.get("forward_to_email")
    )

    host = _as_text(smtp.get("host")) or _as_text(smtp_meta.get("host")) or (
        "email-smtp.us-east-1.amazonaws.com"
    )
    port = _as_text(smtp.get("port")) or _as_text(smtp_meta.get("port")) or "587"
    username = _as_text(smtp.get("username")) or _as_text(smtp_meta.get("username"))
    password = _as_text(smtp.get("password"))

    return f"""Hi,

This is a follow-up to the setup note we sent you on April 29 about your new
cvccboard.org mailbox. We have not yet seen the configuration on our side go
active, so I'm resending the same five-field setup so you can wire it into
your everyday inbox at your own pace.

Your sending mailbox is:   {send_as}
Replies will arrive at:    {inbox}

Add this as a "Send mail as" account inside Gmail (Settings -> Accounts and
Import -> Send mail as -> Add another email address) or as a new SMTP send
account inside Outlook. When it asks for SMTP credentials, use these five
fields exactly:

  1.  SMTP server:    {host}
  2.  Port:           {port}
  3.  Username:       {username}
  4.  Password:       {password}
  5.  From address:   {send_as}

Use TLS (STARTTLS) and require authentication. Gmail will send a short
verification code to {inbox} once you save the credentials -- enter that
code and the mailbox will go live for outbound mail. We do the inbound
side on our end; nothing more is required from you for incoming messages
to land at {inbox}.

If any of this looks off -- wrong forwarding address, prefer a different
personal inbox, want to swap the cvccboard alias -- reply to this message
and we will reissue. The credentials above are scoped only to {send_as}
and can be rotated at any time without changing your personal address.

Thank you,
CVCCBoard mailbox setup
"""


__all__ = [
    "HANDOFF_TEMPLATE_VERSION",
    "handoff_body",
    "handoff_subject",
]
