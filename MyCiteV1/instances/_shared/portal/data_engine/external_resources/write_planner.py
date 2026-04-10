from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mycite_core.mss_resolution import stable_datum_id


@dataclass(frozen=True)
class MaterializationPlan:
    ok: bool
    target_ref: str
    required_refs: list[str]
    existing_local_refs: list[str]
    missing_refs: list[str]
    satisfiable_from_bundle_refs: list[str]
    auto_create_refs: list[str]
    ordered_writes: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "target_ref": self.target_ref,
            "required_refs": list(self.required_refs),
            "existing_local_refs": list(self.existing_local_refs),
            "missing_refs": list(self.missing_refs),
            "satisfiable_from_bundle_refs": list(self.satisfiable_from_bundle_refs),
            "auto_create_refs": list(self.auto_create_refs),
            "ordered_writes": [dict(item) for item in self.ordered_writes],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def _local_ref_set(anthology_payload: dict[str, Any], *, local_msn_id: str) -> set[str]:
    out: set[str] = set()
    rows = anthology_payload.get("rows")
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier = str(row.get("identifier") or row.get("row_id") or "").strip()
        if not identifier:
            continue
        try:
            out.add(stable_datum_id(identifier, local_msn_id=local_msn_id, field_name="identifier"))
        except Exception:
            continue
    return out


def plan_local_materialization(
    *,
    local_msn_id: str,
    anthology_payload: dict[str, Any],
    target_ref: str,
    required_refs: list[str],
    bundle_refs: list[str],
    allow_auto_create: bool,
) -> MaterializationPlan:
    target = stable_datum_id(target_ref, local_msn_id=local_msn_id, field_name="target_ref")
    req = [stable_datum_id(item, local_msn_id=local_msn_id, field_name="required_ref") for item in required_refs if str(item).strip()]
    local_set = _local_ref_set(anthology_payload, local_msn_id=local_msn_id)
    bundle_set = {str(item).strip() for item in bundle_refs if str(item).strip()}

    existing_local = sorted([item for item in req if item in local_set])
    missing = sorted([item for item in req if item not in local_set])
    satisfiable_from_bundle = sorted([item for item in missing if item in bundle_set])
    still_missing = sorted([item for item in missing if item not in bundle_set])
    auto_create = still_missing if allow_auto_create else []
    errors: list[str] = []
    if still_missing and not allow_auto_create:
        errors.append("missing prerequisite abstractions are not satisfiable from bundle and auto_create is disabled")

    writes: list[dict[str, Any]] = []
    for ref in satisfiable_from_bundle:
        writes.append({"action": "materialize_from_bundle", "canonical_ref": ref})
    for ref in auto_create:
        writes.append({"action": "auto_create_prerequisite", "canonical_ref": ref})
    writes.append({"action": "create_target", "canonical_ref": target})

    return MaterializationPlan(
        ok=not errors,
        target_ref=target,
        required_refs=req,
        existing_local_refs=existing_local,
        missing_refs=missing,
        satisfiable_from_bundle_refs=satisfiable_from_bundle,
        auto_create_refs=auto_create,
        ordered_writes=writes,
        warnings=[] if not missing else ["target requires prerequisite closure materialization"],
        errors=errors,
    )
