"""ext_grantee_profile — Phase 9 grantee-profile editor.

One flat form covering identity + paypal + aws_ses + newsletter
sub-configs. Nested keys use a ``.`` separator (e.g.
``paypal.webhook_url``); the save route deserializes them back into the
nested GranteeProfile shape.

The renderer is a thin adapter: it composes the field list and wires
it into ``build_form_component_frame`` (the Phase 7 generic form
component contract). All persistence lives behind
POST ``/__fnd/grantee/save`` (see ``portal_host/app.py``).
"""

from __future__ import annotations

from typing import Any

from ._shared import _as_dict, _as_text


def _build_grantee_profile_form_fields(grantee_dict: dict[str, Any]) -> list[dict[str, Any]]:
    paypal = _as_dict(grantee_dict.get("paypal"))
    aws_ses = _as_dict(grantee_dict.get("aws_ses"))
    newsletter = _as_dict(grantee_dict.get("newsletter"))
    return [
        # Identity
        {
            "key": "label",
            "label": "Display name",
            "type": "text",
            "value": _as_text(grantee_dict.get("label")),
            "required": True,
        },
        {
            "key": "short_name",
            "label": "Short name",
            "type": "text",
            "value": _as_text(grantee_dict.get("short_name")),
        },
        {
            "key": "domains",
            "label": "Domains",
            "type": "string_list",
            "value": list(grantee_dict.get("domains") or []),
            "help_text": "Domains this grantee owns; one per line.",
        },
        {
            "key": "users",
            "label": "Mailbox users",
            "type": "string_list",
            "value": list(grantee_dict.get("users") or []),
            "help_text": "Operator emails who can act on this grantee.",
        },
        # PayPal
        {
            "key": "paypal.webhook_url",
            "label": "PayPal webhook URL",
            "type": "url",
            "value": _as_text(paypal.get("webhook_url")),
            "placeholder": "https://example.org/__fnd/paypal/webhook",
        },
        {
            "key": "paypal.client_id",
            "label": "PayPal client ID",
            "type": "text",
            "value": _as_text(paypal.get("client_id")),
        },
        {
            "key": "paypal.client_secret",
            "label": "PayPal client secret",
            "type": "password",
            "value": _as_text(paypal.get("client_secret")),
            "help_text": "Stored plaintext on disk; restrict POSIX perms.",
        },
        {
            "key": "paypal.environment",
            "label": "PayPal environment",
            "type": "select",
            "value": _as_text(paypal.get("environment")) or "sandbox",
            "options": ["sandbox", "live"],
        },
        # AWS SES
        {
            "key": "aws_ses.region",
            "label": "AWS SES region",
            "type": "text",
            "value": _as_text(aws_ses.get("region")),
            "placeholder": "us-east-1",
        },
        {
            "key": "aws_ses.identity",
            "label": "AWS SES identity",
            "type": "email",
            "value": _as_text(aws_ses.get("identity")),
            "placeholder": "noreply@example.org",
        },
        {
            "key": "aws_ses.smtp_username",
            "label": "AWS SES SMTP username",
            "type": "text",
            "value": _as_text(aws_ses.get("smtp_username")),
        },
        {
            "key": "aws_ses.smtp_password",
            "label": "AWS SES SMTP password",
            "type": "password",
            "value": _as_text(aws_ses.get("smtp_password")),
            "help_text": "Stored plaintext on disk; restrict POSIX perms.",
        },
        # Newsletter
        {
            "key": "newsletter.selected_sender_address",
            "label": "Newsletter sender",
            "type": "email",
            "value": _as_text(newsletter.get("selected_sender_address")),
            "placeholder": "hello@example.org",
        },
        {
            "key": "newsletter.sender_display_name",
            "label": "Sender display name",
            "type": "text",
            "value": _as_text(newsletter.get("sender_display_name")),
        },
        {
            "key": "newsletter.reply_to",
            "label": "Reply-to",
            "type": "email",
            "value": _as_text(newsletter.get("reply_to")),
        },
    ]


def _render_ext_grantee_profile(ctx: dict[str, Any]) -> dict[str, Any]:
    """Returns a payload containing one form_component_frame whose submit_action
    points at POST ``/__fnd/grantee/save``. The frame carries the current
    values of every grantee field; if no grantee is selected, the form is
    omitted and the payload signals ``Select a grantee first``.
    """
    from MyCiteV2.packages.state_machine.nimm.mediate_handlers import (
        build_form_component_frame,
    )

    grantee = _as_dict(ctx.get("grantee"))
    msn_id = _as_text(grantee.get("msn_id"))
    if not msn_id:
        return {
            "grantee_msn_id": "",
            "form_frame": None,
            "empty_message": "Select a grantee to edit its profile.",
        }

    form_frame = build_form_component_frame(
        frame_id="grantee_profile_form",
        label=f"Grantee: {grantee.get('label') or msn_id}",
        intro=(
            "Edit identity, mailbox users, and per-grantee credentials. "
            "Saved values land in the grantee JSON file on disk and are "
            "consumed by the Email, Newsletter, and PayPal extensions."
        ),
        fields=_build_grantee_profile_form_fields(grantee),
        submit_action={
            "route": "/__fnd/grantee/save",
            "schema": "mycite.v2.grantee.save.request.v1",
            "payload": {"msn_id": msn_id},
        },
        submit_label="Save grantee profile",
        target_authority="utilities",
    )
    return {
        "grantee_msn_id": msn_id,
        "form_frame": form_frame,
    }


__all__ = [
    "_build_grantee_profile_form_fields",
    "_render_ext_grantee_profile",
]
