from __future__ import annotations

import hashlib
from typing import Any


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _to_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _is_datum_id(token: str) -> bool:
    parts = token.split("-")
    return len(parts) == 3 and all(part.isdigit() for part in parts)


def _is_numeric_hyphen_token(token: str) -> bool:
    parts = token.split("-")
    return len(parts) >= 2 and all(part.isdigit() for part in parts)


def _is_datum_ref_like(token: str) -> bool:
    raw = _as_text(token)
    if not raw:
        return False
    if "." in raw:
        left, _sep, right = raw.partition(".")
        return _is_numeric_hyphen_token(left) and _is_datum_id(right)
    return _is_datum_id(raw)


def _canonicalize_ref(token: str, *, source_msn_id: str) -> str:
    ref = _as_text(token)
    if not ref:
        return ""
    if "." in ref:
        return ref
    if _is_datum_id(ref) and _as_text(source_msn_id):
        return f"{_as_text(source_msn_id)}.{ref}"
    return ref


def _descriptor_digest(*, resource_id: str, resource_kind: str, bitstring: str) -> str:
    seed = f"{_as_text(resource_id)}|{_as_text(resource_kind)}|{_as_text(bitstring)}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def build_field_ref_bindings(
    refs: list[str],
    *,
    source_msn_id: str,
) -> dict[str, list[str]]:
    all_refs: list[str] = []
    product_profile_refs: list[str] = []
    invoice_log_refs: list[str] = []
    seen: set[str] = set()
    for item in refs:
        canonical = _canonicalize_ref(item, source_msn_id=source_msn_id)
        if not canonical or not _is_datum_ref_like(canonical) or canonical in seen:
            continue
        seen.add(canonical)
        all_refs.append(canonical)
        raw = canonical.lower()
        if raw.endswith(".8-5-1") or ".8-5-" in raw or raw.startswith("8-5-"):
            product_profile_refs.append(canonical)
        if raw.endswith(".8-4-1") or ".8-4-" in raw or raw.startswith("8-4-"):
            invoice_log_refs.append(canonical)
    all_refs = sorted(all_refs)
    product_profile_refs = sorted(product_profile_refs)
    invoice_log_refs = sorted(invoice_log_refs)
    return {
        "all_refs": all_refs,
        "product_profile_refs": product_profile_refs,
        "invoice_log_refs": invoice_log_refs,
    }


def _refs_from_external_bundle(bundle: dict[str, Any], *, source_msn_id: str) -> list[str]:
    out: list[str] = []
    for item in list(bundle.get("isolates") or []):
        if not isinstance(item, dict):
            continue
        canonical = _as_text(item.get("canonical_ref"))
        if canonical:
            out.append(_canonicalize_ref(canonical, source_msn_id=source_msn_id))
            continue
        row = _to_dict(item.get("row"))
        rid = _as_text(row.get("identifier") or row.get("row_id"))
        if rid:
            out.append(_canonicalize_ref(rid, source_msn_id=source_msn_id))
    return out


def select_inherited_binding_for_field(
    *,
    field_id: str,
    field_ref_bindings: dict[str, Any] | None,
) -> dict[str, Any]:
    bindings = _to_dict(field_ref_bindings)
    token = _as_text(field_id)
    fallback = [str(item).strip() for item in list(bindings.get("all_refs") or []) if str(item).strip()]
    if token == "inherited_product_profile_ref":
        preferred = [str(item).strip() for item in list(bindings.get("product_profile_refs") or []) if str(item).strip()]
        if preferred:
            return {"selected_ref": preferred[0], "selection_source": "product_profile_refs", "warnings": []}
        if fallback:
            return {
                "selected_ref": fallback[0],
                "selection_source": "all_refs_fallback",
                "warnings": ["no product_profile_refs found; fell back to all_refs"],
            }
        return {"selected_ref": "", "selection_source": "none", "warnings": ["no candidate inherited refs found"]}
    if token == "inherited_supply_log_ref":
        preferred = [str(item).strip() for item in list(bindings.get("invoice_log_refs") or []) if str(item).strip()]
        if preferred:
            return {"selected_ref": preferred[0], "selection_source": "invoice_log_refs", "warnings": []}
        if fallback:
            return {
                "selected_ref": fallback[0],
                "selection_source": "all_refs_fallback",
                "warnings": ["no invoice_log_refs found; fell back to all_refs"],
            }
        return {"selected_ref": "", "selection_source": "none", "warnings": ["no candidate inherited refs found"]}
    if fallback:
        return {"selected_ref": fallback[0], "selection_source": "all_refs", "warnings": []}
    return {"selected_ref": "", "selection_source": "none", "warnings": ["no candidate inherited refs found"]}


def select_inherited_ref_for_field(
    *,
    field_id: str,
    field_ref_bindings: dict[str, Any] | None,
) -> str:
    selected = select_inherited_binding_for_field(field_id=field_id, field_ref_bindings=field_ref_bindings)
    return _as_text(selected.get("selected_ref"))


def adapt_published_txa_resource_value(
    *,
    payload: dict[str, Any],
    context_source: str,
) -> dict[str, Any]:
    item = _to_dict(payload)
    # Support full singular resource payload and exposed resource-value payload.
    singular = _as_text(item.get("schema")) == "mycite.sandbox.singular_mss_resource.v1"
    if singular:
        resource_id = _as_text(item.get("resource_id"))
        resource_kind = _as_text(item.get("resource_kind") or "txa")
        origin_kind = _as_text(item.get("origin_kind") or "local")
        source_msn_id = _as_text(item.get("source_portal"))
        compile_metadata = _to_dict(item.get("compile_metadata"))
        mss_form = _to_dict(item.get("mss_form"))
        published_value = _to_dict(item.get("published_value"))
    else:
        resource_id = _as_text(item.get("resource_id"))
        resource_kind = _as_text(item.get("resource_kind") or item.get("kind") or "txa")
        origin_kind = _as_text(item.get("origin_kind") or "local")
        source_msn_id = _as_text(item.get("source_msn_id") or item.get("local_msn_id"))
        compile_metadata = _to_dict(item.get("compile_metadata"))
        mss_form = _to_dict(item.get("mss_form"))
        published_value = _to_dict(item.get("published_value"))
    bitstring = _as_text(
        mss_form.get("bitstring")
        or published_value.get("mss_form_bitstring")
        or compile_metadata.get("mss_form_bitstring")
    )
    descriptor = _as_text(
        item.get("descriptor_digest")
        or published_value.get("descriptor_digest")
        or compile_metadata.get("descriptor_digest")
    )
    if not descriptor:
        descriptor = _descriptor_digest(
            resource_id=resource_id,
            resource_kind=resource_kind,
            bitstring=bitstring,
        )
    explicit_bindings = _to_dict(published_value.get("field_ref_bindings"))
    fallback_refs: list[str] = []
    for key in ("resource_ref", "target_ref", "inherited_ref"):
        token = _as_text(published_value.get(key))
        if token:
            fallback_refs.append(token)
    if _as_text(item.get("schema")) == "mycite.external.isolate_bundle.v1":
        fallback_refs.extend(_refs_from_external_bundle(item, source_msn_id=source_msn_id))
    if explicit_bindings:
        bindings = {
            "all_refs": [str(x).strip() for x in list(explicit_bindings.get("all_refs") or []) if str(x).strip()],
            "product_profile_refs": [
                str(x).strip() for x in list(explicit_bindings.get("product_profile_refs") or []) if str(x).strip()
            ],
            "invoice_log_refs": [str(x).strip() for x in list(explicit_bindings.get("invoice_log_refs") or []) if str(x).strip()],
        }
    else:
        bindings = build_field_ref_bindings(fallback_refs, source_msn_id=source_msn_id)
    selected = select_inherited_binding_for_field(field_id="", field_ref_bindings=bindings)
    inherited_resource_ref = _as_text(selected.get("selected_ref"))
    provisional_state = _as_text(item.get("provisional_state") or compile_metadata.get("provisional_state") or "compiled")
    return {
        "ok": bool(resource_id),
        "resource_id": resource_id,
        "resource_kind": resource_kind or "txa",
        "origin_kind": origin_kind or "local",
        "published_value": dict(published_value),
        "mss_form": dict(mss_form),
        "compile_metadata": dict(compile_metadata),
        "descriptor_digest": descriptor,
        "constraint_family": "samras",
        "value_kind": "txa_id",
        "role": "value",
        "field_ref_bindings": bindings,
        "inherited_resource_ref": inherited_resource_ref,
        "binding_selection_source": _as_text(selected.get("selection_source") or "none"),
        "warnings": [str(item).strip() for item in list(selected.get("warnings") or []) if str(item).strip()],
        "provisional_state": provisional_state,
        "context_source": _as_text(context_source) or "published_resource",
    }
