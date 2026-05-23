"""ext_email — AWS SES configuration + mailbox visibility (Email extension).

Reads operator profiles via the AWS peripheral's `ProfileStore` and
surfaces them alongside the grantee's ``aws_ses`` sub-config. Lists
every mailbox across every domain the active grantee owns; per-mailbox
domain is one column in the resulting table.

Architecture: this extension imports only from the AWS peripheral
(`peripherals.aws.ProfileStore`) and never reaches into another
extension. Per-grantee profile state lives in JSON files under
`deployed/<grantee>/private/utilities/tools/aws-csm/aws-csm.*.json`;
no MOS authority is consulted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from datetime import datetime, timedelta, timezone

from MyCiteV2.packages.peripherals.aws import ProfileStore

from ._shared import _as_dict, _as_list, _as_text, _grantee_edit_link, _mask_secret

# Onboarding sequence used both for the per-row progress bar and for the
# Send-reminder gate. Each entry is (key, label, predicate) — predicate
# returns True when the step is complete.
_ONBOARDING_STEPS: tuple[tuple[str, str], ...] = (
    ("profile_created",     "Profile created"),
    ("ses_identity_ready",  "SES identity verified"),
    ("handoff_sent",        "Handoff email sent"),
    ("handoff_acked",       "Operator confirmed credentials"),
    ("inbound_configured",  "Inbound forwarding configured"),
    ("inbound_verified",    "Inbound verified end-to-end"),
)

_REMINDER_COOLDOWN = timedelta(hours=24)


def _onboarding_progress(payload: dict[str, Any]) -> dict[str, Any]:
    """Derive an onboarding-progress summary from a profile JSON payload.

    Returns ``{steps_total, steps_done, percent, completed, next_step}`` where
    ``completed`` is the ordered list of step keys that are done and
    ``next_step`` is the first incomplete (key, label) pair, or ``None`` if
    every step is satisfied.
    """
    workflow = _as_dict(payload.get("workflow"))
    provider = _as_dict(payload.get("provider"))
    inbound = _as_dict(payload.get("inbound"))

    lifecycle_state = _as_text(workflow.get("lifecycle_state")).lower()

    proof: dict[str, bool] = {
        "profile_created": bool(workflow.get("initiated")) or bool(workflow.get("initiated_at")),
        "ses_identity_ready": _as_text(provider.get("aws_ses_identity_status")).lower() == "verified",
        "handoff_sent": bool(_as_text(workflow.get("handoff_email_sent_at"))),
        "handoff_acked": lifecycle_state == "operational" or bool(workflow.get("is_mailbox_operational")),
        "inbound_configured": _as_text(inbound.get("receive_state")).lower() == "receive_configured",
        "inbound_verified": bool(inbound.get("receive_verified")),
    }

    completed: list[str] = []
    next_step: dict[str, str] | None = None
    for key, label in _ONBOARDING_STEPS:
        if proof.get(key):
            completed.append(key)
        elif next_step is None:
            next_step = {"key": key, "label": label}

    total = len(_ONBOARDING_STEPS)
    done = len(completed)
    return {
        "steps_total": total,
        "steps_done": done,
        "percent": int(round(done * 100 / total)) if total else 0,
        "completed": completed,
        "next_step": next_step,
    }


def _parse_iso_ts(value: str) -> datetime | None:
    txt = _as_text(value)
    if not txt:
        return None
    # Accept trailing 'Z' as UTC indicator (Python <3.11 fromisoformat doesn't).
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        ts = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _reminder_cooldown_remaining(workflow: dict[str, Any]) -> timedelta | None:
    """Return time remaining in the 24h reminder cooldown, or None if elapsed.

    Used both by the per-row button gate (UI) and by the POST route (server)
    so a user can't bypass the cooldown by hand-rolling a request.
    """
    last = _parse_iso_ts(_as_text(workflow.get("reminder_sent_at")))
    if last is None:
        return None
    now = datetime.now(timezone.utc)
    elapsed = now - last
    if elapsed >= _REMINDER_COOLDOWN:
        return None
    return _REMINDER_COOLDOWN - elapsed


def _build_email_extension_payload(
    grantee: dict[str, Any],
    domain: str,
    private_dir: str | Path | None,
    authority_db_file: str | Path | None = None,
    portal_instance_id: str | None = None,
) -> dict[str, Any]:
    aws_subconfig = _as_dict(grantee.get("aws_ses"))
    configuration = {
        "label": "AWS SES configuration",
        "summary": "Identity, region, and SMTP credentials. Edit in the Grantee Profile.",
        "items": [
            {"label": "Region", "value": _as_text(aws_subconfig.get("region"))},
            {"label": "Identity", "value": _as_text(aws_subconfig.get("identity"))},
            {"label": "SMTP username", "value": _as_text(aws_subconfig.get("smtp_username"))},
            {"label": "SMTP password", "value": _mask_secret(aws_subconfig.get("smtp_password"))},
        ],
        "edit_link": _grantee_edit_link("aws_ses"),
    }

    # Phase 16c: take the union of the grantee's registered domains
    # AND the currently-selected ``domain`` (in case the operator
    # picked a domain that isn't in the grantee list yet). Lowercased
    # for case-insensitive identity matching downstream.
    grantee_domains = {
        _as_text(d).lower() for d in _as_list(grantee.get("domains")) if _as_text(d)
    }
    if domain:
        grantee_domains.add(domain.lower())
    if not grantee_domains or private_dir is None:
        return {"profiles": [], "domain": domain, "configuration": configuration}

    # Profiles live as JSON files at
    # ``<private>/utilities/tools/aws-csm/aws-csm.<scope>.<mailbox>.json``;
    # `ProfileStore` globs `aws-csm.*.json` under that root. No MOS.
    tool_root = Path(private_dir) / "utilities" / "tools" / "aws-csm"
    store = ProfileStore(root=tool_root)

    # The configuration block uses the active domain's record (when
    # available) so SES identity / region / SMTP creds shown above
    # reflect the operator's primary domain. The profiles list below
    # spans ALL of the grantee's domains.
    domain_record: dict[str, Any] = {}
    if domain:
        try:
            domain_record = _as_dict(store.get_domain(domain))
        except Exception:
            domain_record = {}

    profiles: list[dict[str, Any]] = []
    try:
        operator_source = store.list_profiles()
        for payload in operator_source:
            ident = _as_dict(payload.get("identity"))
            profile_domain = _as_text(ident.get("domain")).lower()
            if profile_domain not in grantee_domains:
                continue
            profile_id = _as_text(ident.get("profile_id"))
            lifecycle = _as_text(
                _as_dict(payload.get("workflow")).get("lifecycle_state")
            )
            workflow = _as_dict(payload.get("workflow"))
            inbox_target = _as_text(ident.get("operator_inbox_target"))
            progress = _onboarding_progress(payload)
            profiles.append({
                "profile_id": profile_id,
                "domain": profile_domain,
                "mailbox": _as_text(ident.get("mailbox_local_part")),
                "send_as": _as_text(ident.get("send_as_email")),
                "role": _as_text(ident.get("role")),
                "lifecycle": lifecycle,
                "inbound": _as_text(
                    _as_dict(payload.get("inbound")).get("receive_state")
                ),
                "onboarding_progress": progress,
                "suspend_action": _suspend_action_for_profile(profile_id, lifecycle),
                "resend_handoff_action": _resend_handoff_action_for_profile(
                    profile_id, lifecycle, inbox_target
                ),
                "send_reminder_action": _send_reminder_action_for_profile(
                    profile_id, lifecycle, inbox_target, workflow, progress
                ),
                "handoff_email_sent_at": _as_text(workflow.get("handoff_email_sent_at")),
                "reminder_sent_at": _as_text(workflow.get("reminder_sent_at")),
            })
        # Stable ordering: by domain, then mailbox local part — keeps
        # cvcc.admin / cvcc.finance / cvccboard.daniel / etc. grouped
        # so the operator can scan the table predictably.
        profiles.sort(key=lambda r: (r["domain"], r["mailbox"]))
    except Exception:
        pass
    return {
        "domain": domain,
        "domains": sorted(grantee_domains),
        "profiles": profiles,
        "domain_record": domain_record,
        "configuration": configuration,
    }


def _suspend_action_for_profile(profile_id: str, lifecycle: str) -> dict[str, Any]:
    """Per-row toggle button. Suspended rows resume to ``operational``;
    everything else (``operational``, empty, etc.) becomes ``suspended``.
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    is_suspended = lifecycle.lower() == "suspended"
    if is_suspended:
        return {
            "label": "Resume",
            "route": "/__fnd/email/admin/suspend",
            "schema": "mycite.v2.email.admin.suspend.request.v1",
            "payload": {"profile_id": profile_id, "suspended": False},
            "variant": "secondary",
        }
    return {
        "label": "Suspend",
        "route": "/__fnd/email/admin/suspend",
        "schema": "mycite.v2.email.admin.suspend.request.v1",
        "payload": {"profile_id": profile_id, "suspended": True},
        "confirm": f"Suspend mailbox {profile_id}?",
        "variant": "danger",
    }


def _resend_handoff_action_for_profile(
    profile_id: str, lifecycle: str, inbox_target: str
) -> dict[str, Any]:
    """Per-row "Resend handoff" button.

    Visible only while the mailbox is still in draft / instruction_sent
    state — i.e. lifecycle is empty or ``draft``. Operational and
    suspended rows do not need a resend.
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    state = _as_text(lifecycle).lower()
    if state in {"operational", "suspended"}:
        return {}
    target_label = _as_text(inbox_target) or "the configured inbox"
    return {
        "label": "Resend handoff",
        "route": "/__fnd/email/admin/resend-handoff",
        "schema": "mycite.v2.email.admin.resend_handoff.request.v1",
        "payload": {"profile_id": profile_id},
        "confirm": f"Resend handoff email for {profile_id} to {target_label}?",
        "variant": "secondary",
    }


def _send_reminder_action_for_profile(
    profile_id: str,
    lifecycle: str,
    inbox_target: str,
    workflow: dict[str, Any],
    progress: dict[str, Any],
) -> dict[str, Any]:
    """Per-row "Send onboarding reminder" button.

    Distinct from "Resend handoff": resend-handoff re-sends the SMTP
    credentials package. A reminder is a polite nudge — no credentials —
    for mailboxes where the handoff was already sent but the operator
    hasn't completed the next step yet.

    Gates:
      - handoff_email_sent_at must be non-empty (no handoff, no reminder)
      - lifecycle must not be operational / suspended
      - the onboarding sequence must still have a next_step
      - if a reminder was sent within the last 24h, return the button in a
        disabled state with the remaining cooldown so the operator sees the
        cooldown without trial-clicking
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    state = _as_text(lifecycle).lower()
    if state in {"operational", "suspended"}:
        return {}
    if not _as_text(workflow.get("handoff_email_sent_at")):
        return {}
    if not progress.get("next_step"):
        return {}

    target_label = _as_text(inbox_target) or "the configured inbox"
    next_step_label = (progress.get("next_step") or {}).get("label") or "the next step"

    base = {
        "label": "Send reminder",
        "route": "/__fnd/email/admin/send-reminder",
        "schema": "mycite.v2.email.admin.send_reminder.request.v1",
        "payload": {"profile_id": profile_id},
        "confirm": (
            f"Send onboarding reminder for {profile_id} to {target_label}? "
            f"It will nudge them to complete: {next_step_label}."
        ),
        "variant": "secondary",
    }

    cooldown = _reminder_cooldown_remaining(workflow)
    if cooldown is not None:
        hours = max(1, int(round(cooldown.total_seconds() / 3600)))
        base["disabled"] = True
        base["label"] = f"Sent recently ({hours}h cooldown)"
        base["confirm"] = None
    return base


def _render_ext_aws_email(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_email_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
    )


__all__ = [
    "_build_email_extension_payload",
    "_onboarding_progress",
    "_render_ext_aws_email",
    "_resend_handoff_action_for_profile",
    "_send_reminder_action_for_profile",
    "_reminder_cooldown_remaining",
]
