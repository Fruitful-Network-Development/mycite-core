from __future__ import annotations

from .base import RuleContext, RuleDefinition, as_text, make_ui_state


def build_samras_rule() -> RuleDefinition:
    def _match(context: RuleContext) -> bool:
        return as_text(context.row.reference) == "0-0-5"

    def _derive(_context: RuleContext) -> dict[str, object]:
        return {"family_scope": "structural_value", "root_ref": "0-0-5"}

    def _validate(_context: RuleContext, _constraints: dict[str, object]) -> tuple[bool, list[str], list[str]]:
        # SAMRAS structural-value semantics are owned by samras modules.
        return True, ["delegated to SAMRAS structural engine"], []

    def _ui(_context: RuleContext, _constraints: dict[str, object]) -> dict[str, object]:
        return make_ui_state("standard", family="samras", transitional=False)

    return RuleDefinition(
        key="samras.separate_family.v1",
        family="samras",
        lens_key="lens.samras.structure.v1",
        allowed_parent_families=(),
        transitional=False,
        match=_match,
        derive_constraints=_derive,
        validate=_validate,
        ui_hints=_ui,
    )
