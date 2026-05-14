"""Utilities-tab extension dispatch.

Phase 12g (drift remediation) extracts the per-extension renderer wrappers,
the grantee profile form, and the EXTENSION_RENDERERS dispatch table out of
the legacy `portal_fnd_csm_runtime.py` (which is named for a tool surface
retired in Phase 3g but still hosts the legacy bundle path under preservation
invariant). The underlying `_build_*_extension_payload` core builders stay
in `portal_fnd_csm_runtime.py` for one transition cycle: the legacy bundle
path under `build_portal_fnd_csm_surface_bundle` continues to consume them
directly, and full per-extension extraction is deferred to a future commit
so this phase remains low-risk.

Public surface (the only symbols Utilities callers should import from
this package):

  * EXTENSION_RENDERERS — dict keyed by extension tool_id mapping to a
    renderer `(ctx: dict) -> dict`. The keys must match `is_extension=True`
    entries in `build_portal_tool_registry_entries()`; the
    `test_extension_renderer_parity.py` postcondition pins the bijection.
  * render_extension(tool_id, ctx) — resilient dispatch wrapper that
    returns `{}` on unknown tool_id or renderer exception so the
    Utilities surface payload never crashes on a mis-registered
    extension.

Each renderer is a thin adapter: it extracts the keys it needs from `ctx`
(grantee dict, domain string, private_dir, authority_db_file,
portal_instance_id) and delegates to the corresponding builder in
`portal_fnd_csm_runtime.py`. The grantee_profile renderer additionally
composes the form frame inline via Phase 7's `build_form_component_frame`.
"""

from __future__ import annotations

from typing import Any

from MyCiteV2.instances._shared.runtime.portal_fnd_csm_runtime import (
    _as_dict,
    _as_text,
    _build_analytics_extension_payload,
    _build_email_extension_payload,
    _build_newsletter_extension_payload,
    _build_paypal_extension_payload,
)


def _render_ext_aws_email(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_email_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _render_ext_analytics(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_analytics_extension_payload(
        domain=_as_text(ctx.get("domain")),
        webapps_root=ctx.get("webapps_root"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _render_ext_newsletter(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_newsletter_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _render_ext_paypal(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_paypal_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


def _build_grantee_profile_form_fields(grantee_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Field list for the grantee profile form.

    Phase 9 (grantee_profile_contract.md): one flat form covering identity
    + paypal + aws_ses + newsletter sub-configs. Nested keys use a "."
    separator (e.g. "paypal.webhook_url"); the save route deserializes
    them back into the nested GranteeProfile shape.
    """
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
    """Phase 9 renderer for the grantee-profile editor.

    Returns a payload containing one form_component_frame whose submit_action
    points at POST /__fnd/grantee/save. The frame carries the current values
    of every grantee field; if no grantee is selected, the form is omitted
    and the payload signals "select a grantee first".
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


EXTENSION_RENDERERS: dict[str, Any] = {
    "ext_aws_email": _render_ext_aws_email,
    "ext_analytics": _render_ext_analytics,
    "ext_newsletter": _render_ext_newsletter,
    "ext_paypal": _render_ext_paypal,
    "ext_grantee_profile": _render_ext_grantee_profile,
}


def render_extension(tool_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Render an extension by tool_id with the given context dict.

    Returns an empty dict for unknown tool_ids rather than raising; this keeps
    the utilities surface bundle resilient when an extension is mis-registered.
    Required context keys vary by extension; see _render_ext_* for specifics.
    """
    renderer = EXTENSION_RENDERERS.get(_as_text(tool_id))
    if renderer is None:
        return {}
    try:
        return renderer(ctx)
    except Exception:
        return {}


__all__ = ["EXTENSION_RENDERERS", "render_extension"]
