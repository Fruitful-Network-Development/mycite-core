"""ext_email — onboarding-progress + reminder helpers (Email extension).

The operator-facing Email extension *surface*
(``_build_email_extension_payload`` plus its per-row edit / remove /
suspend / resend-handoff / send-reminder action builders and the onboarding
legend) was removed when the FND-CSM operator apparatus was dissolved
(portal-tool-overlay-restructure).

What remains here are the pure derivation helpers the live ``/__fnd/email``
routes still import: ``_onboarding_progress`` + ``_onboarding_aws_evidence``
(onboarding-stage derivation, including the Wave-B AWS evidence probes) and
``_reminder_cooldown_remaining`` (the 24h reminder gate the
``/__fnd/email/admin/send-reminder`` route re-checks server-side). The
overlay-adapter resolver is kept alongside since the probe helpers depend on
it. No MOS authority is consulted.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from MyCiteV2.packages.peripherals.aws import ProbeCache

from ._shared import _as_dict, _as_text

# B2 — module-level cache for the Wave-B activity-based onboarding overlay
# probes. Single instance shared across requests in this worker process;
# 5-minute TTL so the email tab doesn't trigger an SES/CloudWatch/S3
# round-trip per mailbox per page render. Cleared on process restart.
_OVERLAY_PROBE_CACHE: ProbeCache = ProbeCache(ttl_seconds=300)

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

_REMINDER_COOLDOWN = timedelta(hours=24)


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
        "percent": round(done * 100 / total) if total else 0,
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
        ts = ts.replace(tzinfo=UTC)
    return ts


def _reminder_cooldown_remaining(workflow: dict[str, Any]) -> timedelta | None:
    """Return time remaining in the 24h reminder cooldown, or None if elapsed.

    Used both by the per-row button gate (UI) and by the POST route (server)
    so a user can't bypass the cooldown by hand-rolling a request.
    """
    last = _parse_iso_ts(_as_text(workflow.get("reminder_sent_at")))
    if last is None:
        return None
    now = datetime.now(UTC)
    elapsed = now - last
    if elapsed >= _REMINDER_COOLDOWN:
        return None
    return _REMINDER_COOLDOWN - elapsed


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


__all__ = [
    "_OVERLAY_PROBE_CACHE",
    "_onboarding_aws_evidence",
    "_onboarding_progress",
    "_reminder_cooldown_remaining",
]
