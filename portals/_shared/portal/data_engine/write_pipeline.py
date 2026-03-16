from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from _shared.portal.datum_refs import parse_datum_ref
from .field_contracts import default_profile_field_contracts
from .geometry_datums import geometry_template_spec, validate_template_fields
from .profile_config_refs import append_unique_path_value, get_path, set_path


@dataclass(frozen=True)
class WritePreviewResult:
    ok: bool
    intent: dict[str, Any]
    validation: dict[str, Any]
    plan: dict[str, Any]
    config_updates: list[dict[str, Any]]
    write_actions: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "intent": dict(self.intent),
            "validation": dict(self.validation),
            "plan": dict(self.plan),
            "config_updates": [dict(item) for item in self.config_updates],
            "write_actions": [dict(item) for item in self.write_actions],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class WriteApplyResult:
    ok: bool
    created_datum_refs: list[str]
    updated_config_refs: list[dict[str, Any]]
    mutation_summary: dict[str, Any]
    contract_mss_sync: dict[str, Any]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "created_datum_refs": list(self.created_datum_refs),
            "updated_config_refs": [dict(item) for item in self.updated_config_refs],
            "mutation_summary": dict(self.mutation_summary),
            "contract_mss_sync": dict(self.contract_mss_sync),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _canonical_ref(local_ref: str, local_msn_id: str) -> str:
    token = _as_text(local_ref)
    if not token:
        return ""
    if "." in token:
        return token
    msn = _as_text(local_msn_id)
    return f"{msn}.{token}" if msn else token


def _local_ref_from_canonical(canonical_ref: str) -> str:
    parsed = parse_datum_ref(canonical_ref)
    return parsed.datum_address if parsed is not None else _as_text(canonical_ref)


def _iter_anthology_identifiers(anthology_payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    rows = anthology_payload.get("rows") if isinstance(anthology_payload, dict) else []
    if isinstance(rows, dict):
        out.update(str(key).strip() for key in rows.keys() if str(key).strip())
        return out
    if isinstance(rows, list):
        for item in rows:
            if isinstance(item, dict):
                rid = _as_text(item.get("id") or item.get("identifier") or item.get("row_id"))
                if rid:
                    out.add(rid)
    return out


def _ref_exists_locally(canonical_ref: str, anthology_payload: dict[str, Any]) -> bool:
    token = _local_ref_from_canonical(canonical_ref)
    if not token:
        return False
    return token in _iter_anthology_identifiers(anthology_payload)


def _build_default_required_refs(intent: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("taxonomy_ref", "resource_ref", "parent_ref", "boundary_ref", "parcel_ref", "field_ref", "plot_ref", "inherited_ref"):
        token = _as_text((intent.get("fields") or {}).get(key))
        if token:
            out.append(token)
    return out


def preview_write_intent(
    *,
    intent: dict[str, Any],
    current_config: dict[str, Any],
    local_anthology_payload: dict[str, Any] | None = None,
    external_plan_fn: Callable[[dict[str, Any]], tuple[bool, dict[str, Any], str]],
) -> WritePreviewResult:
    intent_type = _as_text(intent.get("intent_type"))
    template_id = _as_text(intent.get("template_id"))
    fields = intent.get("fields") if isinstance(intent.get("fields"), dict) else {}
    errors: list[str] = []
    warnings: list[str] = []
    local_msn_id = _as_text(intent.get("local_msn_id"))

    contracts = default_profile_field_contracts()
    contract = None
    field_id = _as_text(intent.get("field_id"))
    write_mode = _as_text(intent.get("write_mode") or "create_new_local_datum")
    if intent_type == "profile_field":
        contract = contracts.get(field_id)
        if contract is None:
            errors.append(f"unknown field contract: {field_id}")
        else:
            if write_mode not in set(contract.write_modes):
                errors.append(f"write_mode '{write_mode}' is not allowed for field '{field_id}'")
            if template_id and contract.allowed_template_ids and template_id not in set(contract.allowed_template_ids):
                warnings.append(f"template_id '{template_id}' is not typical for field '{field_id}'")
            contract_errors, contract_warnings = contract.validate_fields(fields)
            errors.extend(contract_errors)
            warnings.extend(contract_warnings)
    if intent_type not in {"profile_field", "geometry_datum", "agro_template"}:
        errors.append(f"unsupported intent_type: {intent_type}")

    template_spec = geometry_template_spec(template_id)
    if not template_spec and intent_type in {"geometry_datum", "agro_template"}:
        errors.append(f"unknown template_id: {template_id}")
    elif template_spec:
        template_errors, template_warnings = validate_template_fields(template_id, fields)
        errors.extend(template_errors)
        warnings.extend(template_warnings)

    inherited_ref = _as_text(fields.get("inherited_ref") or intent.get("inherited_ref"))
    if write_mode == "stage_inherited_ref":
        if not inherited_ref:
            errors.append("inherited_ref is required for write_mode='stage_inherited_ref'")
        local_id = _as_text(intent.get("target_ref"))
        target_ref = _canonical_ref(inherited_ref or local_id, local_msn_id)
    else:
        local_id = _as_text(fields.get("local_id") or intent.get("local_id") or intent.get("target_ref"))
        if not local_id:
            errors.append("local_id is required")
        target_ref = _canonical_ref(local_id, local_msn_id)
    required_refs = [str(item).strip() for item in list(intent.get("required_refs") or []) if str(item).strip()]
    if not required_refs:
        required_refs = _build_default_required_refs(intent)
    required_refs = sorted(set(item for item in required_refs if item))

    external_ok = True
    external_plan: dict[str, Any] = {}
    external_error = ""
    source_msn_id = _as_text(intent.get("source_msn_id"))
    resource_id = _as_text(intent.get("resource_id"))
    if source_msn_id and resource_id:
        external_ok, external_plan, external_error = external_plan_fn(
            {
                "source_msn_id": source_msn_id,
                "resource_id": resource_id,
                "target_ref": local_id,
                "required_refs": required_refs,
                "allow_auto_create": bool(intent.get("allow_auto_create", True)),
            }
        )
        if not external_ok:
            errors.append(external_error or "external planner failed")
    elif intent_type == "agro_template":
        warnings.append("no external source/resource configured for this intent")

    write_actions: list[dict[str, Any]] = []
    external_writes = external_plan.get("ordered_writes") if isinstance(external_plan, dict) else []
    local_payload = local_anthology_payload if isinstance(local_anthology_payload, dict) else {}
    if isinstance(external_writes, list):
        for item in external_writes:
            if not isinstance(item, dict):
                continue
            action = dict(item)
            canonical_ref = _as_text(action.get("canonical_ref"))
            if canonical_ref and _ref_exists_locally(canonical_ref, local_payload):
                write_actions.append(
                    {"action": "reuse_existing_prerequisite", "canonical_ref": canonical_ref, "source_action": action.get("action")}
                )
            else:
                write_actions.append(action)
    if write_mode == "stage_inherited_ref":
        write_actions.append(
            {
                "action": "stage_inherited_ref",
                "canonical_ref": target_ref,
                "materialization": "none",
            }
        )
    elif target_ref and _ref_exists_locally(target_ref, local_payload):
        write_actions.append({"action": "reuse_existing_target", "canonical_ref": target_ref})
    else:
        write_actions.append({"action": "create_target", "canonical_ref": target_ref})

    config_updates: list[dict[str, Any]] = []
    if contract is not None:
        current = get_path(current_config, contract.target_path)
        if contract.multi_value:
            existing = current if isinstance(current, list) else []
            next_value = sorted(set([str(item) for item in existing if str(item).strip()] + [target_ref]))
        else:
            next_value = target_ref
        config_updates.append(
            {"path": contract.target_path, "previous": current, "next": next_value, "update_scope": contract.update_scope}
        )

    return WritePreviewResult(
        ok=not errors,
        intent={
            "intent_type": intent_type,
            "template_id": template_id,
            "field_id": field_id,
            "write_mode": write_mode,
            "local_msn_id": local_msn_id,
            "target_ref": target_ref,
            "fields": dict(fields),
        },
        validation={
            "required_refs": required_refs,
            "contract": contract.to_dict() if contract is not None else {},
            "template_spec": dict(template_spec),
            "target_ref_exists_locally": bool(target_ref and _ref_exists_locally(target_ref, local_payload)),
        },
        plan={"ordered_writes": write_actions, "external_plan": dict(external_plan)},
        config_updates=config_updates,
        write_actions=write_actions,
        warnings=warnings,
        errors=errors,
    )


def apply_write_preview(
    *,
    preview: WritePreviewResult,
    workspace: Any,
    load_config_fn: Callable[[], dict[str, Any]],
    save_config_fn: Callable[[dict[str, Any]], bool],
) -> WriteApplyResult:
    if not preview.ok:
        return WriteApplyResult(
            ok=False,
            created_datum_refs=[],
            updated_config_refs=[],
            mutation_summary={},
            contract_mss_sync={},
            warnings=[],
            errors=["cannot apply invalid preview"],
        )

    template_spec = preview.validation.get("template_spec") if isinstance(preview.validation, dict) else {}
    layer = int((template_spec or {}).get("layer") or 20)
    value_group = int((template_spec or {}).get("value_group") or 1)
    reference = _as_text((template_spec or {}).get("reference")) or "0-0-1"
    fields = preview.intent.get("fields") if isinstance(preview.intent.get("fields"), dict) else {}

    created_refs: list[str] = []
    reused_refs: list[str] = []
    last_contract_sync: dict[str, Any] = {}
    warnings: list[str] = []
    errors: list[str] = []
    mutation_rows: list[dict[str, Any]] = []

    for action in preview.write_actions:
        kind = _as_text(action.get("action"))
        canonical_ref = _as_text(action.get("canonical_ref"))
        if kind in {"reuse_existing_target", "reuse_existing_prerequisite"}:
            if canonical_ref:
                reused_refs.append(canonical_ref)
            mutation_rows.append({"action": kind, "identifier": canonical_ref, "result": {"ok": True, "reused": True}})
            continue
        if kind == "stage_inherited_ref":
            if canonical_ref:
                reused_refs.append(canonical_ref)
            mutation_rows.append(
                {
                    "action": kind,
                    "identifier": canonical_ref,
                    "result": {"ok": True, "reused": True, "materialization": "none"},
                }
            )
            continue
        if kind == "create_target":
            magnitude_payload = {
                "template_id": preview.intent.get("template_id"),
                "field_id": preview.intent.get("field_id"),
                "canonical_ref": canonical_ref,
                **fields,
            }
            result = workspace.append_anthology_datum(
                layer=layer,
                value_group=value_group,
                reference=reference,
                magnitude=json.dumps(magnitude_payload, separators=(",", ":")),
                label=_as_text(fields.get("title")) or canonical_ref or "datum",
            )
            if not bool(result.get("ok")):
                errors.extend([str(item) for item in list(result.get("errors") or [])] or ["failed to append target datum"])
                break
            identifier = _as_text(result.get("identifier"))
            if identifier:
                created_refs.append(identifier)
            mutation_rows.append({"action": kind, "identifier": identifier, "result": result})
            cms = result.get("contract_mss_sync")
            if isinstance(cms, dict):
                last_contract_sync = dict(cms)
            warnings.extend([str(item) for item in list(result.get("warnings") or [])])
            continue

        if kind in {"materialize_from_bundle", "auto_create_prerequisite"}:
            result = workspace.append_anthology_datum(
                layer=layer,
                value_group=value_group,
                reference="0-0-1",
                magnitude=json.dumps({"canonical_ref": canonical_ref, "source_action": kind}, separators=(",", ":")),
                label=f"Prerequisite {canonical_ref}",
            )
            if not bool(result.get("ok")):
                errors.extend([str(item) for item in list(result.get("errors") or [])] or [f"failed to apply action: {kind}"])
                break
            identifier = _as_text(result.get("identifier"))
            if identifier:
                created_refs.append(identifier)
            mutation_rows.append({"action": kind, "identifier": identifier, "result": result})
            cms = result.get("contract_mss_sync")
            if isinstance(cms, dict):
                last_contract_sync = dict(cms)
            warnings.extend([str(item) for item in list(result.get("warnings") or [])])

    config_updates: list[dict[str, Any]] = []
    if not errors and preview.config_updates:
        config_payload = load_config_fn() or {}
        for update in preview.config_updates:
            path = _as_text(update.get("path"))
            next_value = update.get("next")
            if isinstance(next_value, list):
                for item in next_value:
                    config_payload = append_unique_path_value(config_payload, path, item)
            else:
                config_payload = set_path(config_payload, path, next_value)
            config_updates.append({"path": _as_text(update.get("path")), "next": update.get("next")})
        if not save_config_fn(config_payload):
            errors.append("failed to persist config updates")

    return WriteApplyResult(
        ok=not errors,
        created_datum_refs=created_refs + reused_refs,
        updated_config_refs=config_updates,
        mutation_summary={
            "mutation_count": len(mutation_rows),
            "created_count": len(created_refs),
            "reused_count": len(reused_refs),
            "mutations": mutation_rows,
        },
        contract_mss_sync=last_contract_sync,
        warnings=warnings,
        errors=errors,
    )
