from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from _shared.portal.data_engine.rules import (
    derive_rule_policy,
    evaluate_resource_payload_write,
    extract_rows_payload_from_resource_body,
    understand_datums,
)


@dataclass(frozen=True)
class WorkbenchRulesService:
    def evaluate_resource_payload(
        self,
        payload: dict[str, Any],
        *,
        rule_write_override: bool = False,
        rule_write_override_reason: str = "",
    ) -> dict[str, Any] | None:
        schema = str(payload.get("schema") or "").strip().lower()
        if schema.startswith("mycite.sandbox.singular_mss_resource"):
            return None
        if schema.startswith("mycite.sandbox.mss_resource"):
            return None
        if schema.startswith("mycite.sandbox.mss_compact_array"):
            return None
        rows_payload = extract_rows_payload_from_resource_body(payload)
        if rows_payload is None:
            return None
        evaluation = evaluate_resource_payload_write(rows_payload, rule_write_override=rule_write_override)
        if rule_write_override and not rule_write_override_reason:
            evaluation.setdefault("warnings", []).append("rule_write_override used without rule_write_override_reason")
        return evaluation

    def understanding_for_resource_body(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        rows_payload = extract_rows_payload_from_resource_body(payload)
        if rows_payload is None:
            return None, None
        rows = rows_payload.get("rows") if isinstance(rows_payload.get("rows"), dict) else {}
        if not rows:
            return None, None
        report = understand_datums(rows_payload)
        return report.to_dict(), {key: derive_rule_policy(value).to_dict() for key, value in report.by_id.items()}
