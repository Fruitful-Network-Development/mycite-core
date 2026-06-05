"""ext_newsletter — contact log + sender configuration for the grantee.

Reads the contact log and newsletter sender profile for the domain.
When ``authority_db_file`` is provided, the contact log is sourced from
the MOS v2 datum (``fnd_newsletter_contact_log_<domain>``). Profile
reads stay on the filesystem adapter regardless.

Phase 14d.1 extends the payload with three operator-facing controls:

  * ``admin_forms[add_subscriber]`` — form_component_frame for adding
    a subscriber. Submits to ``POST /__fnd/newsletter/admin/add``.
  * ``admin_forms[set_sender]`` — form_component_frame for picking the
    newsletter sender from ``grantee.users``. Submits to
    ``POST /__fnd/newsletter/admin/set_sender``.
  * ``contact_rows[].remove_action`` — per-row ``{label, route,
    payload}`` triple the JS renderer wires as a button. Subscribed
    rows get an "Unsubscribe" action; unsubscribed rows get a
    re-subscribe action.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemNewsletterStateAdapter
from MyCiteV2.packages.state_machine.nimm.mediate_handlers import (
    build_form_component_frame,
)

from ._shared import _as_dict, _as_list, _as_text, _grantee_edit_link


def _build_add_subscriber_form(domain: str) -> dict[str, Any]:
    return build_form_component_frame(
        frame_id="newsletter_add_subscriber",
        label="Add subscriber",
        intro="Insert an operator-driven subscription. Public sign-ups still flow through /__fnd/newsletter/subscribe.",
        fields=[
            {"key": "email", "label": "Email", "type": "email", "required": True},
            # Phase 15b: split name fields so the operator-entered data
            # matches the CSV-imported rows from the legacy intake.
            {"key": "first_name", "label": "First name", "type": "text", "required": False},
            {"key": "middle_name", "label": "Middle name", "type": "text", "required": False},
            {"key": "last_name", "label": "Last name", "type": "text", "required": False},
            # Phase 16a: phone + zip captured as plain text. signup_date
            # is omitted from the add form — it defaults to today on
            # the mutation runtime side.
            {"key": "phone", "label": "Phone", "type": "text", "required": False},
            {"key": "zip", "label": "ZIP", "type": "text", "required": False},
        ],
        submit_action={
            "route": "/__fnd/newsletter/admin/add",
            "schema": "mycite.v2.newsletter.admin.add.request.v1",
            "payload": {"domain": domain},
        },
        submit_label="Add subscriber",
        target_authority="newsletter_contact_log",
    )


def _edit_action_for_contact(domain: str, contact: dict[str, Any]) -> dict[str, Any]:
    """Phase 16a per-row edit. Carries the current field values so the
    JS renderer can pre-fill the inline form, and the route + schema
    for POSTing the updated values.
    """
    return {
        "label": "Edit",
        "route": "/__fnd/newsletter/admin/edit",
        "schema": "mycite.v2.newsletter.admin.edit.request.v1",
        "payload": {
            "domain": domain,
            "fields": {"email": _as_text(contact.get("email"))},
        },
        "variant": "secondary",
        "editable_fields": [
            {"key": "first_name", "label": "First name", "value": _as_text(contact.get("first_name"))},
            {"key": "middle_name", "label": "Middle name", "value": _as_text(contact.get("middle_name"))},
            {"key": "last_name", "label": "Last name", "value": _as_text(contact.get("last_name"))},
            {"key": "phone", "label": "Phone", "value": _as_text(contact.get("phone"))},
            {"key": "zip", "label": "ZIP", "value": _as_text(contact.get("zip"))},
            {"key": "signup_date", "label": "Signup date", "value": _as_text(contact.get("signup_date"))},
        ],
    }


def _build_set_sender_form(msn_id: str, users: list[str], current_sender: str) -> dict[str, Any] | None:
    options = [{"value": u, "label": u} for u in users if _as_text(u)]
    if not options:
        return None
    return build_form_component_frame(
        frame_id="newsletter_set_sender",
        label="Change newsletter sender",
        intro="Pick the operator address that signs outgoing newsletters. Persists to the grantee JSON.",
        fields=[
            {
                "key": "sender_address",
                "label": "Sender",
                "type": "select",
                "value": current_sender or (options[0]["value"] if options else ""),
                "options": options,
                "required": True,
            }
        ],
        submit_action={
            "route": "/__fnd/newsletter/admin/set_sender",
            "schema": "mycite.v2.newsletter.admin.set_sender.request.v1",
            "payload": {"msn_id": msn_id},
        },
        submit_label="Set as sender",
        target_authority="grantee_profile",
    )


def _remove_action_for_contact(domain: str, email: str, subscribed: bool) -> dict[str, Any]:
    if subscribed:
        return {
            "label": "Unsubscribe",
            "route": "/__fnd/newsletter/admin/remove",
            "schema": "mycite.v2.newsletter.admin.remove.request.v1",
            "payload": {"domain": domain, "fields": {"email": email}},
            "confirm": f"Unsubscribe {email}?",
            "variant": "danger",
        }
    return {
        "label": "Re-subscribe",
        "route": "/__fnd/newsletter/admin/add",
        "schema": "mycite.v2.newsletter.admin.add.request.v1",
        "payload": {"domain": domain, "fields": {"email": email}},
        "variant": "secondary",
    }


def _build_newsletter_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    newsletter_subconfig = _as_dict(grantee.get("newsletter"))
    msn_id = _as_text(grantee.get("msn_id"))
    users = [_as_text(u) for u in _as_list(grantee.get("users")) if _as_text(u)]
    configuration = {
        "label": "Newsletter configuration",
        "summary": "Sender address, display name, and reply-to. Edit in the Grantee Profile.",
        "items": [
            {"label": "Sender address", "value": _as_text(newsletter_subconfig.get("selected_sender_address"))},
            {"label": "Display name", "value": _as_text(newsletter_subconfig.get("sender_display_name"))},
            {"label": "Reply-to", "value": _as_text(newsletter_subconfig.get("reply_to"))},
        ],
        "edit_link": _grantee_edit_link("newsletter"),
    }
    admin_forms: list[dict[str, Any]] = []
    if domain:
        admin_forms.append(_build_add_subscriber_form(domain))
    set_sender_form = _build_set_sender_form(
        msn_id, users, _as_text(newsletter_subconfig.get("selected_sender_address"))
    )
    if set_sender_form is not None:
        admin_forms.append(set_sender_form)

    if not domain or private_dir is None:
        return {
            "domain": domain,
            "sender_options": users,
            "current_sender": "",
            "contact_rows": [],
            "configuration": configuration,
            "admin_forms": admin_forms,
        }
    contacts: list[dict[str, Any]] = []
    current_sender = ""
    try:
        adapter = FilesystemNewsletterStateAdapter(private_dir)
        # Newsletter contact state lives in JSON under
        # `<private>/utilities/tools/newsletter/`; no MOS authority is
        # consulted (extensions read grantee/extension JSON files only).
        contacts_payload = _as_dict(adapter.load_contact_log(domain=domain))
        raw_contacts = _as_list(contacts_payload.get("contacts"))
        contacts = []
        for c in raw_contacts:
            if not (isinstance(c, dict) and _as_text(c.get("email"))):
                continue
            first = _as_text(c.get("first_name"))
            middle = _as_text(c.get("middle_name"))
            last = _as_text(c.get("last_name"))
            display = (
                " ".join(t for t in (first, last) if t)
                or " ".join(t for t in (first, middle, last) if t)
                or _as_text(c.get("name"))
            )
            row = {
                "email": _as_text(c.get("email")),
                "name": display,
                "first_name": first,
                "middle_name": middle,
                "last_name": last,
                "phone": _as_text(c.get("phone")),
                "zip": _as_text(c.get("zip")),
                "signup_date": _as_text(c.get("signup_date")),
                "subscribed": bool(c.get("subscribed")),
                "source": _as_text(c.get("source")),
                "last_sent": _as_text(c.get("last_newsletter_sent_at")),
                "send_count": int(c.get("send_count") or 0),
                "remove_action": _remove_action_for_contact(
                    domain, _as_text(c.get("email")), bool(c.get("subscribed"))
                ),
            }
            row["edit_action"] = _edit_action_for_contact(domain, c)
            contacts.append(row)
        profile = _as_dict(adapter.load_profile(domain=domain))
        current_sender = _as_text(
            profile.get("selected_sender_address") or profile.get("sender_address")
        ).lower()
    except Exception:
        pass
    return {
        "domain": domain,
        "sender_options": users,
        "current_sender": current_sender,
        "contact_rows": contacts,
        "subscribed_count": sum(1 for c in contacts if c.get("subscribed")),
        "unsubscribed_count": sum(1 for c in contacts if not c.get("subscribed")),
        "configuration": configuration,
        "admin_forms": admin_forms,
    }


def _render_ext_newsletter(ctx: dict[str, Any]) -> dict[str, Any]:
    from ._global import global_stub, is_global

    if is_global(ctx):
        return global_stub("Newsletter")
    return _build_newsletter_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = ["_build_newsletter_extension_payload", "_render_ext_newsletter"]
