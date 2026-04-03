"""Engine-owned rule policy derived from ``DatumUnderstanding.status`` (frozen v2).

Routes and services use ``RulePolicy`` for write/picker/lens behavior; UI consumes
the same payloads. Classification and warnings always apply; only ``invalid`` is
blocked by default (rules still evolving — ``ambiguous`` / ``unknown`` stay writable).

Status → policy defaults (v2)
-----------------------------
``standard``
    Writes allowed; guided/filtered reference UI by default; lens active.

``transitional``
    Writes allowed; guided UI + engine/list warnings; publish discouraged.

``ambiguous``
    Writes allowed; strong UI + API warnings; visually distinct; prefer guided
    picks when inference exists; manual/freeform always available — no override
    required for normal users.

``unknown``
    Writes allowed; neutral/manual path; warn clearly; not treated as invalid.

``invalid``
    Writes blocked by default; error lens; ``rule_write_override`` for explicit
    admin bypass when justified.
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
    guidance_notes: tuple[str, ...] = ()

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
            "guidance_notes": list(self.guidance_notes),
            "schema": "mycite.portal.datum_rules.rule_policy.v2",
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
            guidance_notes=(),
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
            guidance_notes=(
                "transitional rule family state: review engine warnings before publish",
            ),
        )
    if status == "ambiguous":
        return RulePolicy(
            status=status,
            family=family,
            rule_key=rule_key,
            create_mode="evolving",
            edit_mode="evolving",
            ref_mode="guided_prefer_filtered",
            lens_mode="degraded",
            requires_manual_override=False,
            write_allowed=True,
            can_create=True,
            can_edit=True,
            can_pick_refs=True,
            can_save=True,
            can_publish=False,
            can_use_default_lens=True,
            guidance_notes=(
                "ambiguous rule classification — edits allowed while rules evolve",
                "prefer filtered reference lists when the engine can infer them; manual entry remains available",
            ),
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
            guidance_notes=(
                "invalid under current rule constraints — fix datum shape/refs or use explicit admin override",
            ),
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
        guidance_notes=(
            "no matching rule family — neutral/manual editing; confirm references against live anthology/resource rows",
        ),
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
