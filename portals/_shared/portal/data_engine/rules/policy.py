"""Engine-owned rule policy derived from ``DatumUnderstanding.status`` (frozen v1).

This is not a UI skin: routes and services should use ``RulePolicy`` to decide
whether writes, reference picking, and lens usage are permitted. UI consumes the
same payloads returned by the API.

Status → policy defaults (v1)
----------------------------
``standard``
    Normal create/edit; references should use filtered engine lists; lens active;
    writes allowed.

``transitional``
    Limited create/edit; lens active; warnings expected; publish discouraged;
    writes still allowed (caller may surface warnings).

``ambiguous``
    Writes blocked unless ``rule_write_override``; reference picking blocked
    unless manual/admin path; lens degraded.

``invalid``
    Writes blocked unless ``rule_write_override``; error lens / error state;
    no default filtered refs.

``unknown``
    Neutral / manual mode only: writes allowed without family-specific
    assumptions; freeform reference entry is the default; no family lens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import DatumUnderstanding, as_text


@dataclass(frozen=True)
class RulePolicy:
    """Behavior contract for a single understood datum (engine-owned)."""

    status: str
    family: str
    rule_key: str
    create_mode: str
    edit_mode: str
    ref_mode: str
    lens_mode: str
    requires_manual_override: bool
    write_allowed: bool
    can_create: bool
    can_edit: bool
    can_pick_refs: bool
    can_save: bool
    can_publish: bool
    can_use_default_lens: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "family": self.family,
            "rule_key": self.rule_key,
            "create_mode": self.create_mode,
            "edit_mode": self.edit_mode,
            "ref_mode": self.ref_mode,
            "lens_mode": self.lens_mode,
            "requires_manual_override": self.requires_manual_override,
            "write_allowed": self.write_allowed,
            "can_create": self.can_create,
            "can_edit": self.can_edit,
            "can_pick_refs": self.can_pick_refs,
            "can_save": self.can_save,
            "can_publish": self.can_publish,
            "can_use_default_lens": self.can_use_default_lens,
            "schema": "mycite.portal.datum_rules.rule_policy.v1",
        }


def derive_rule_policy(understanding: DatumUnderstanding | None) -> RulePolicy:
    """Map a concrete understanding (or ``None``) to a frozen policy."""
    if understanding is None:
        return _unknown_policy(family="none", rule_key="none", status="unknown")

    status = as_text(understanding.status) or "unknown"
    family = as_text(understanding.family) or "none"
    rule_key = as_text(understanding.rule_key) or "none"

    if status == "standard":
        return RulePolicy(
            status=status,
            family=family,
            rule_key=rule_key,
            create_mode="normal",
            edit_mode="normal",
            ref_mode="filtered_default",
            lens_mode="active",
            requires_manual_override=False,
            write_allowed=True,
            can_create=True,
            can_edit=True,
            can_pick_refs=True,
            can_save=True,
            can_publish=True,
            can_use_default_lens=True,
        )
    if status == "transitional":
        return RulePolicy(
            status=status,
            family=family,
            rule_key=rule_key,
            create_mode="limited",
            edit_mode="limited",
            ref_mode="filtered_default",
            lens_mode="active",
            requires_manual_override=False,
            write_allowed=True,
            can_create=True,
            can_edit=True,
            can_pick_refs=True,
            can_save=True,
            can_publish=False,
            can_use_default_lens=True,
        )
    if status == "ambiguous":
        return RulePolicy(
            status=status,
            family=family,
            rule_key=rule_key,
            create_mode="blocked",
            edit_mode="blocked",
            ref_mode="blocked",
            lens_mode="degraded",
            requires_manual_override=True,
            write_allowed=False,
            can_create=False,
            can_edit=False,
            can_pick_refs=False,
            can_save=False,
            can_publish=False,
            can_use_default_lens=False,
        )
    if status == "invalid":
        return RulePolicy(
            status=status,
            family=family,
            rule_key=rule_key,
            create_mode="blocked",
            edit_mode="blocked",
            ref_mode="blocked",
            lens_mode="error",
            requires_manual_override=True,
            write_allowed=False,
            can_create=False,
            can_edit=False,
            can_pick_refs=False,
            can_save=False,
            can_publish=False,
            can_use_default_lens=False,
        )
    # unknown (or unrecognized token): neutral manual path
    return _unknown_policy(family=family, rule_key=rule_key, status="unknown")


def _unknown_policy(*, family: str, rule_key: str, status: str) -> RulePolicy:
    return RulePolicy(
        status=status,
        family=family,
        rule_key=rule_key,
        create_mode="neutral",
        edit_mode="neutral",
        ref_mode="manual_default",
        lens_mode="none",
        requires_manual_override=False,
        write_allowed=True,
        can_create=True,
        can_edit=True,
        can_pick_refs=True,
        can_save=True,
        can_publish=False,
        can_use_default_lens=False,
    )


def gate_write_attempt(
    policy: RulePolicy,
    *,
    rule_write_override: bool,
    hint_validation_ok: bool | None = None,
) -> tuple[bool, list[str]]:
    """Return (permitted, messages). ``hint_validation_ok`` is optional stricter rule_key pass."""
    notes: list[str] = []
    if hint_validation_ok is False:
        if rule_write_override:
            notes.append("rule_write_override: rule_key hint validation failed but override was applied")
            return True, notes
        return False, ["rule_key hint validation failed"]

    if policy.write_allowed:
        return True, notes

    if rule_write_override:
        notes.append("rule_write_override: write was blocked by rule policy but override was applied")
        return True, notes

    return False, [f"write blocked by rule policy (status={policy.status})"]


__all__ = [
    "RulePolicy",
    "derive_rule_policy",
    "gate_write_attempt",
]
