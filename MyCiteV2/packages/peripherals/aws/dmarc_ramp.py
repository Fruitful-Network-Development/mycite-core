"""C3 — DMARC policy ramp ladder + parsing helpers.

The DMARC enforcement ladder is intentionally conservative, mirroring
the active-task guardrail G-1 from
``2026-05-22.email_deliverability_and_portal_onboarding``:

  p=none
    -> p=quarantine; pct=20      (after MAIL FROM live + 7d + >=95% align)
  p=quarantine; pct=20
    -> p=quarantine; pct=100     (after another 7d + >=95% align)
  p=quarantine; pct=100
    -> p=reject                  (after another 7d + >=95% align)
  p=reject
    -> (terminal — no further ramp)

Premature DMARC tightening is the #1 way self-managed email goes dark:
a p=reject before alignment is confirmed bounces every mis-aligned
legitimate message. So every rung requires BOTH a dwell time AND an
alignment threshold; the ramp NEVER skips a rung (no p=none -> p=reject).

This module is pure (no AWS / no IO) so the ladder is unit-testable in
isolation. The adapter methods that read/write the live _dmarc TXT live
in cloud_adapter.py and call into here.
"""

from __future__ import annotations

import re
from typing import Any

# Minimum dwell + alignment to advance one rung. Tunable but conservative.
MIN_DWELL_DAYS = 7
MIN_ALIGNMENT_PCT = 95.0


def parse_dmarc_policy(txt_record: str) -> dict[str, str]:
    """Parse a DMARC TXT record value into its tags.

    Accepts the raw record with or without surrounding quotes. Returns a
    dict of lowercased tag -> value (e.g. {"v": "DMARC1", "p": "none",
    "pct": "100", "rua": "mailto:..."}). ``pct`` defaults to "100" per
    RFC 7489 when absent. An unparseable / non-DMARC record returns {}.
    """
    text = (txt_record or "").strip().strip('"').strip()
    if "v=DMARC1" not in text.replace(" ", "").replace("v=DMARC1", "v=DMARC1"):
        # Fast reject: must contain the DMARC1 version tag.
        if "dmarc1" not in text.lower():
            return {}
    tags: dict[str, str] = {}
    for part in text.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        tags[key.strip().lower()] = value.strip()
    if tags.get("v", "").lower() != "dmarc1":
        return {}
    tags.setdefault("pct", "100")
    return tags


def _rung(policy: str, pct: str) -> str:
    """Canonical rung name from (p, pct)."""
    policy = (policy or "").lower()
    if policy == "none":
        return "none"
    if policy == "quarantine":
        return "quarantine_20" if str(pct) == "20" else "quarantine_100"
    if policy == "reject":
        return "reject"
    return "unknown"


# Ordered ladder: each rung -> the next rung's (p, pct) target.
_NEXT_RUNG: dict[str, tuple[str, str] | None] = {
    "none": ("quarantine", "20"),
    "quarantine_20": ("quarantine", "100"),
    "quarantine_100": ("reject", "100"),
    "reject": None,            # terminal
    "unknown": ("none", "100"),  # repair: unknown -> reset to p=none
}


def compute_dmarc_ramp(
    *,
    current_tags: dict[str, str],
    mail_from_live: bool,
    alignment_pct: float | None,
    days_at_current: int | None,
) -> dict[str, Any]:
    """Decide whether (and to what) the DMARC policy may advance.

    Returns:
      {
        "current_rung": str,
        "current_policy": str,      # the p= value
        "current_pct": str,
        "proposed_policy": str|None,  # p= for the next rung, or None at terminal
        "proposed_pct": str|None,
        "proposed_record": str|None,  # the full TXT value to UPSERT, or None
        "allowed": bool,            # True only when every precondition met
        "blockers": list[str],      # why not, when allowed is False
      }

    `allowed` is True only when ALL hold:
      * there IS a next rung (not terminal / not unknown-repair)
      * mail_from_live is True
      * alignment_pct >= MIN_ALIGNMENT_PCT
      * days_at_current >= MIN_DWELL_DAYS
    """
    current_policy = (current_tags.get("p") or "").lower()
    current_pct = str(current_tags.get("pct") or "100")
    # No DMARC record at all (empty tags) is the BOTTOM of the ladder, not a
    # malformed record. parse_dmarc_policy returns {} both when there's no
    # _dmarc TXT yet and when the record is non-DMARC garbage; treat the
    # empty case as the "none" rung so a freshly-onboarded domain (which
    # sync_domain_dns seeds at p=none anyway) can ramp, instead of being
    # told to "fix manually". A PRESENT-but-unrecognized p= still routes to
    # 'unknown' below.
    if not current_tags:
        current_rung = "none"
        current_policy = "none"
    else:
        current_rung = _rung(current_policy, current_pct)

    nxt = _NEXT_RUNG.get(current_rung)
    blockers: list[str] = []

    if current_rung == "reject":
        return {
            "current_rung": current_rung,
            "current_policy": current_policy,
            "current_pct": current_pct,
            "proposed_policy": None,
            "proposed_pct": None,
            "proposed_record": None,
            "allowed": False,
            "blockers": ["already at terminal policy p=reject"],
        }
    if current_rung == "unknown":
        # Repair path is intentionally NOT auto-applied — flag for operator.
        blockers.append(
            f"current DMARC policy unrecognized (p={current_policy!r}); "
            "fix manually rather than auto-ramping"
        )

    proposed_policy, proposed_pct = (nxt or (None, None))

    if not mail_from_live:
        blockers.append("custom MAIL FROM is not live for this domain")
    if alignment_pct is None:
        blockers.append("no alignment data available yet (need aggregate reports)")
    elif alignment_pct < MIN_ALIGNMENT_PCT:
        blockers.append(
            f"alignment {alignment_pct:.1f}% < required {MIN_ALIGNMENT_PCT:.0f}%"
        )
    if days_at_current is None:
        blockers.append("unknown dwell time at current policy")
    elif days_at_current < MIN_DWELL_DAYS:
        blockers.append(
            f"only {days_at_current}d at current policy; need >= {MIN_DWELL_DAYS}d"
        )

    allowed = (
        current_rung not in ("reject", "unknown")
        and proposed_policy is not None
        and not blockers
    )

    proposed_record = None
    if proposed_policy is not None:
        rua = current_tags.get("rua") or (
            "mailto:dmarc-reports@fruitfulnetworkdevelopment.com"
        )
        # Preserve strict alignment tags; build the proposed record.
        pct_clause = "" if proposed_pct == "100" else f" pct={proposed_pct};"
        proposed_record = (
            f"v=DMARC1; p={proposed_policy};{pct_clause} "
            f"rua={rua}; adkim=s; aspf=s"
        )

    return {
        "current_rung": current_rung,
        "current_policy": current_policy,
        "current_pct": current_pct,
        "proposed_policy": proposed_policy,
        "proposed_pct": proposed_pct,
        "proposed_record": proposed_record,
        "allowed": allowed,
        "blockers": blockers,
    }


__all__ = [
    "MIN_ALIGNMENT_PCT",
    "MIN_DWELL_DAYS",
    "compute_dmarc_ramp",
    "parse_dmarc_policy",
]
