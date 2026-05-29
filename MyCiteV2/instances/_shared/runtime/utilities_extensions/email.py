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

import logging
import time
from pathlib import Path
from typing import Any

from datetime import datetime, timedelta, timezone

from MyCiteV2.packages.peripherals.aws import ProbeCache, ProfileStore

_log = logging.getLogger("mycite.portal_host")

from ._shared import _as_dict, _as_list, _as_text, _grantee_edit_link, _mask_secret


# B2 — module-level cache for the Wave-B activity-based onboarding overlay
# probes. Single instance shared across requests in this worker process;
# 5-minute TTL so the email tab doesn't trigger an SES/CloudWatch/S3
# round-trip per mailbox per page render. Cleared on process restart.
_OVERLAY_PROBE_CACHE: ProbeCache = ProbeCache(ttl_seconds=300)

# Per-render wall-clock budget for live AWS probes. The email extension
# renders inside a 5.0s ThreadPoolExecutor future (portal_shell_runtime);
# a cold cache on a multi-mailbox grantee could otherwise issue 3*N
# sequential AWS round-trips and blow that timeout, degrading the WHOLE
# extension to a placeholder. Once elapsed, remaining mailboxes render
# flag-only (no badges) and warm the cache incrementally across renders —
# cache hits are cheap, so subsequent renders reach further before the
# budget bites. 3.0s leaves headroom under the 5.0s future timeout.
_OVERLAY_PROBE_BUDGET_SECONDS = 3.0

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

# Steps whose AWS evidence is DIRECT enough to auto-advance the flag when
# the evidence is positive but the JSON flag isn't set yet. ses_identity_ready
# (SES VerificationStatus) and inbound_verified (an S3 inbound object exists)
# are direct proof. handoff_acked is intentionally absent — its probe is the
# operator-sends proxy, which is shown as a badge but must never flip the step
# on its own (see _onboarding_progress).
_AUTO_ADVANCE_STEPS: frozenset[str] = frozenset(
    {"ses_identity_ready", "inbound_verified"}
)

# Plain-English meaning per step. Surfaced in the email extension card as
# a static legend table above the Mailboxes table so an operator scanning
# a "2 of 6" progress bar can tell what the remaining steps are without
# digging into JSON.
_ONBOARDING_STEP_DESCRIPTIONS: dict[str, str] = {
    "profile_created":     "Operator profile JSON exists with workflow.initiated set.",
    "ses_identity_ready":  "AWS SES verified the send-as identity (DKIM signed, sending enabled).",
    "handoff_sent":        "Onboarding handoff email (SMTP credentials + setup link) was dispatched.",
    "handoff_acked":       "Operator confirmed receipt — lifecycle flipped to operational.",
    "inbound_configured":  "Inbound SES rule + S3/Lambda forwarder wired for the mailbox.",
    "inbound_verified":    "A live inbound message was received and forwarded end-to-end.",
}

_REMINDER_COOLDOWN = timedelta(hours=24)


def _build_onboarding_legend() -> list[dict[str, str]]:
    """Return the static legend rows for the onboarding-stage table.

    Each row is ``{step, stage, meaning}`` — `stage` is what the operator
    sees in the progress-bar tooltip, `meaning` explains what "complete"
    means in concrete terms. Order matches `_ONBOARDING_STEPS` so the
    table reads top-to-bottom in the same order completion advances.
    """
    return [
        {
            "step": str(idx + 1),
            "key": key,
            "stage": label,
            "meaning": _ONBOARDING_STEP_DESCRIPTIONS.get(key, ""),
        }
        for idx, (key, label) in enumerate(_ONBOARDING_STEPS)
    ]


def _onboarding_aws_evidence(
    payload: dict[str, Any],
    *,
    aws_adapter: Any,
    cache: ProbeCache | None = None,
    deadline: float | None = None,
) -> dict[str, dict[str, str]]:
    """B2 — call the 3 AwsPeripheralCloudAdapter probes for the steps that
    have live AWS evidence (steps 2 / 4 / 6) and return a dict keyed by
    step key with each probe's AwsEvidence triple. Steps with no live
    probe (1 / 3 / 5) are absent from the returned dict.

    Each probe result is cached for the lifetime of the module's
    `_OVERLAY_PROBE_CACHE` TTL keyed by (probe_name, send_as_email/domain,
    declared_flag) so an N-mailbox grantee triggers AT MOST 3*N round
    trips on a cold render and 0 on a warm one.

    ``deadline`` is a ``time.monotonic()`` value (per-render budget shared
    across all mailboxes in one payload build). Once it's passed, this
    mailbox renders flag-only (no probes) so the extension can't exceed
    its 5s render future on a cold multi-mailbox grantee.
    """
    if aws_adapter is None:
        return {}
    if deadline is not None and time.monotonic() > deadline:
        return {}
    if cache is None:
        cache = _OVERLAY_PROBE_CACHE

    ident = _as_dict(payload.get("identity"))
    workflow = _as_dict(payload.get("workflow"))
    provider = _as_dict(payload.get("provider"))
    inbound = _as_dict(payload.get("inbound"))

    send_as = _as_text(ident.get("send_as_email")).lower()
    domain = _as_text(ident.get("domain")).lower()
    declared_ses_verified = _as_text(provider.get("aws_ses_identity_status")).lower() == "verified"
    lifecycle_state = _as_text(workflow.get("lifecycle_state")).lower()
    declared_operational = (
        lifecycle_state == "operational" or bool(workflow.get("is_mailbox_operational"))
    )
    declared_inbound_verified = bool(inbound.get("receive_verified"))

    evidence: dict[str, dict[str, str]] = {}
    if send_as:
        evidence["ses_identity_ready"] = cache.get_or_compute(
            ("ses_identity", send_as, declared_ses_verified),
            lambda: aws_adapter.probe_ses_identity_aws_evidence(
                send_as, declared_verified=declared_ses_verified
            ),
        )
        evidence["handoff_acked"] = cache.get_or_compute(
            ("operator_sends", send_as, declared_operational),
            lambda: aws_adapter.probe_operator_sends_aws_evidence(
                send_as, declared_operational=declared_operational
            ),
        )
    if domain:
        evidence["inbound_verified"] = cache.get_or_compute(
            ("inbound_verified", domain, declared_inbound_verified),
            lambda: aws_adapter.probe_inbound_verified_aws_evidence(
                domain, declared_verified=declared_inbound_verified
            ),
        )
    return evidence


def _onboarding_progress(
    payload: dict[str, Any],
    *,
    aws_adapter: Any | None = None,
    probe_deadline: float | None = None,
) -> dict[str, Any]:
    """Derive an onboarding-progress summary from a profile JSON payload.

    Returns ``{steps_total, steps_done, percent, completed, next_step,
    aws_evidence}`` — `aws_evidence` is a dict keyed by step key
    carrying the {state, detail, observed_at} triple from the Wave-B
    probes; empty {} when ``aws_adapter`` is None (the existing
    flag-only behavior — kept as the default so existing callers + tests
    don't break).

    B2 auto-advance: when a step's AWS evidence is ``auto_advance``
    (positive evidence but the declared flag is unset), the step counts
    as ``completed`` for percent / next_step purposes. ``drift`` /
    ``absent`` / ``error`` do NOT change the flag-based proof.
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

    aws_evidence = _onboarding_aws_evidence(
        payload, aws_adapter=aws_adapter, deadline=probe_deadline
    )
    for step_key, evidence in aws_evidence.items():
        if step_key in _AUTO_ADVANCE_STEPS and evidence.get("state") == "auto_advance":
            proof[step_key] = True
        # confirmed / drift / absent / error don't override the flag —
        # confirmed agrees with the flag (already True); drift is the UI
        # warning signal but doesn't move the percent; absent + error
        # leave the flag's truth alone.
        #
        # handoff_acked is deliberately NOT in _AUTO_ADVANCE_STEPS: its
        # probe (operator SES sends) is an INDIRECT proxy for "operator
        # acknowledged the handoff", so we show its badge but never let it
        # flip the step complete on its own — otherwise, once a per-identity
        # send metric exists, a single outbound send would inflate the
        # progress bar past a handoff the operator never confirmed.

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
        "aws_evidence": aws_evidence,
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
    aws_adapter: Any | None = None,
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
        return {
            "profiles": [],
            "domain": domain,
            "configuration": configuration,
            "onboarding_legend": _build_onboarding_legend(),
        }

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
            _log.warning("email_domain_record_load_failed", exc_info=True)
            domain_record = {}

    profiles: list[dict[str, Any]] = []
    # One shared probe budget for the whole mailbox list this render, so the
    # extension can't exceed its 5s render future on a cold multi-mailbox
    # grantee. Only meaningful when probes are live (aws_adapter set).
    probe_deadline = (
        time.monotonic() + _OVERLAY_PROBE_BUDGET_SECONDS
        if aws_adapter is not None
        else None
    )
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
            progress = _onboarding_progress(
                payload, aws_adapter=aws_adapter, probe_deadline=probe_deadline
            )
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
                "edit_action": _edit_action_for_profile(profile_id, ident),
                "suspend_action": _suspend_action_for_profile(profile_id, lifecycle),
                "resend_handoff_action": _resend_handoff_action_for_profile(
                    profile_id, lifecycle, inbox_target
                ),
                "send_reminder_action": _send_reminder_action_for_profile(
                    profile_id, lifecycle, inbox_target, workflow, progress
                ),
                "remove_action": _remove_action_for_profile(profile_id),
                "handoff_email_sent_at": _as_text(workflow.get("handoff_email_sent_at")),
                "reminder_sent_at": _as_text(workflow.get("reminder_sent_at")),
            })
        # Stable ordering: by domain, then mailbox local part — keeps
        # cvcc.admin / cvcc.finance / cvccboard.daniel / etc. grouped
        # so the operator can scan the table predictably.
        profiles.sort(key=lambda r: (r["domain"], r["mailbox"]))
    except Exception:
        _log.warning("email_mailbox_profiles_load_failed", exc_info=True)
        pass
    return {
        "domain": domain,
        "domains": sorted(grantee_domains),
        "profiles": profiles,
        "domain_record": domain_record,
        "configuration": configuration,
        "onboarding_legend": _build_onboarding_legend(),
    }


def _edit_action_for_profile(
    profile_id: str, identity: dict[str, Any]
) -> dict[str, Any]:
    """Per-row inline edit on the mailbox profile table.

    Editable fields are the cosmetic / routing fields the operator legitimately
    needs to tweak after the mailbox is alive — send_as_email, role, and
    operator_inbox_target. Identity primary keys (profile_id, domain,
    mailbox_local_part, tenant_id) are NOT editable inline; changing them would
    desynchronize the JSON filename, SES identity registration, and forwarder
    map all at once, which is a re-onboard, not an edit.
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    return {
        "label": "Edit",
        "route": "/__fnd/email/admin/edit",
        "schema": "mycite.v2.email.admin.edit.request.v1",
        "payload": {
            "profile_id": profile_id,
            "fields": {},
        },
        "variant": "secondary",
        "editable_fields": [
            {
                "key": "send_as_email",
                "label": "Send-as email",
                "value": _as_text(identity.get("send_as_email")),
            },
            {
                "key": "role",
                "label": "Role",
                "value": _as_text(identity.get("role")),
            },
            {
                "key": "operator_inbox_target",
                "label": "Operator inbox",
                "value": _as_text(identity.get("operator_inbox_target")),
            },
        ],
    }


def _remove_action_for_profile(profile_id: str) -> dict[str, Any]:
    """Per-row "Remove" button.

    Deletes the on-disk profile JSON. Strong confirmation required because
    this is destructive — the operator's mailbox is unaffected at the SES
    level, but the portal forgets every workflow timestamp + lifecycle
    state until the profile is re-bootstrapped. Use Suspend for a
    reversible "stop using this" toggle.
    """
    profile_id = _as_text(profile_id)
    if not profile_id:
        return {}
    return {
        "label": "Remove",
        "route": "/__fnd/email/admin/remove",
        "schema": "mycite.v2.email.admin.remove.request.v1",
        "payload": {"profile_id": profile_id},
        "confirm": (
            f"Remove profile {profile_id}? This deletes the on-disk "
            "JSON. SES identity + inbound rules are NOT touched. Use "
            "Suspend instead for a reversible disable."
        ),
        "variant": "danger",
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


def _resolve_overlay_adapter(ctx: dict[str, Any]) -> Any | None:
    """Pick the AwsPeripheralCloudAdapter for the Wave-B overlay probes.

    Precedence:
      1. ``ctx["aws_adapter"]`` — caller-injected (tests, future surface
         wiring). Honored even if None (so tests can disable probes
         explicitly by passing aws_adapter=None in ctx).
      2. Otherwise lazy-create an adapter unless the env var
         ``MYCITE_DISABLE_EMAIL_OVERLAY_PROBES=1`` is set (kill switch
         when AWS perms are temporarily broken in production).

    The adapter is cached per-process via ``_lazy_adapter`` so we don't
    pay boto3 client construction cost on every render.
    """
    if "aws_adapter" in ctx:
        return ctx.get("aws_adapter")
    import os
    if (os.environ.get("MYCITE_DISABLE_EMAIL_OVERLAY_PROBES") or "").strip() == "1":
        return None
    return _lazy_overlay_adapter()


_LAZY_OVERLAY_ADAPTER: Any | None = None


def _lazy_overlay_adapter() -> Any:
    global _LAZY_OVERLAY_ADAPTER
    if _LAZY_OVERLAY_ADAPTER is None:
        from MyCiteV2.packages.peripherals.aws import AwsPeripheralCloudAdapter
        _LAZY_OVERLAY_ADAPTER = AwsPeripheralCloudAdapter()
    return _LAZY_OVERLAY_ADAPTER


def _render_ext_aws_email(ctx: dict[str, Any]) -> dict[str, Any]:
    return _build_email_extension_payload(
        grantee=_as_dict(ctx.get("grantee")),
        domain=_as_text(ctx.get("domain")),
        private_dir=ctx.get("private_dir"),
        authority_db_file=ctx.get("authority_db_file"),
        portal_instance_id=ctx.get("portal_instance_id"),
        aws_adapter=_resolve_overlay_adapter(ctx),
    )


__all__ = [
    "_OVERLAY_PROBE_CACHE",
    "_build_email_extension_payload",
    "_build_onboarding_legend",
    "_edit_action_for_profile",
    "_onboarding_aws_evidence",
    "_onboarding_progress",
    "_remove_action_for_profile",
    "_render_ext_aws_email",
    "_resend_handoff_action_for_profile",
    "_send_reminder_action_for_profile",
    "_reminder_cooldown_remaining",
]
