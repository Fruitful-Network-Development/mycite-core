"""ext_connect — Connect-form submissions + forward configuration.

Phase 17b: the Connect extension is the operator-facing view for
website-visitor Connect-form submissions. It reads the same
newsletter contact log used by ext_newsletter but filters to
``source=connect_form`` so the operator sees only the lead-collection
rows, with each row's subject + message + forward_status visible
inline.

Configuration block exposes the grantee's
``connect.forward_to_email`` (edited via the Grantee Profile tab)
since that's the address the FND portal forwards messages to.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from MyCiteV2.packages.adapters.filesystem import FilesystemNewsletterStateAdapter

_log = logging.getLogger("mycite.portal_host")

from ._shared import _as_dict, _as_list, _as_text, _grantee_edit_link


def _build_connect_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    connect_subconfig = _as_dict(grantee.get("connect"))
    forward_to_email = _as_text(connect_subconfig.get("forward_to_email"))
    configuration = {
        "label": "Connect configuration",
        "summary": (
            "Visitor messages from the website Connect form are forwarded "
            "to this address via SES. Edit in the Grantee Profile."
        ),
        "items": [
            {"label": "Forward-to email", "value": forward_to_email or "(not configured)"},
        ],
        "edit_link": _grantee_edit_link("connect"),
    }

    if not domain or private_dir is None:
        return {
            "domain": domain,
            "forward_to_email": forward_to_email,
            "submissions": [],
            "configuration": configuration,
        }

    contacts: list[dict[str, Any]] = []
    try:
        # Single canonical store — the same tree every contact writer now
        # uses. (``authority_db_file`` is accepted for call-site compat but no
        # longer selects a separate adapter / doubled directory.)
        adapter = FilesystemNewsletterStateAdapter(private_dir)
        contacts_payload = _as_dict(adapter.load_contact_log(domain=domain))
        contacts = _as_list(contacts_payload.get("contacts"))
    except Exception:
        _log.warning("connect_contact_log_load_failed", exc_info=True)
        contacts = []

    submissions: list[dict[str, Any]] = []
    for c in contacts:
        if not isinstance(c, dict):
            continue
        if _as_text(c.get("source")) != "connect_form":
            continue
        first = _as_text(c.get("first_name"))
        last = _as_text(c.get("last_name"))
        display = " ".join(t for t in (first, last) if t) or _as_text(c.get("name"))
        submissions.append(
            {
                "email": _as_text(c.get("email")),
                "name": display,
                "first_name": first,
                "middle_name": _as_text(c.get("middle_name")),
                "last_name": last,
                "phone": _as_text(c.get("phone")),
                "zip": _as_text(c.get("zip")),
                "subject": _as_text(c.get("subject")),
                "message": _as_text(c.get("message")),
                "forward_status": _as_text(c.get("forward_status")) or "—",
                "signup_date": _as_text(c.get("signup_date")),
                "subscribed_to_newsletter": bool(c.get("subscribed")),
            }
        )
    submissions.sort(key=lambda r: r.get("signup_date", ""), reverse=True)

    return {
        "domain": domain,
        "forward_to_email": forward_to_email,
        "submissions": submissions,
        "submission_count": len(submissions),
        "configuration": configuration,
        "notice": (
            "Configure ``connect.forward_to_email`` in the Grantee Profile to enable "
            "message forwarding. Until set, Connect-form submissions land in the "
            "list below but no email is sent."
            if not forward_to_email
            else ""
        ),
    }


def _render_ext_connect(ctx: dict[str, Any]) -> dict[str, Any]:
    from ._global import build_overall_roster, is_global

    if is_global(ctx):
        return build_overall_roster(
            ctx,
            extension_label="Connect",
            summarize=lambda g: (
                "connect configured" if g.get("connect") else "not configured"
            ),
        )
    return _build_connect_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = ["_build_connect_extension_payload", "_render_ext_connect"]
