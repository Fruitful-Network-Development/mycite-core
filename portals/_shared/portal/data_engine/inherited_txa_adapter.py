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
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        all_refs.append(canonical)
        raw = canonical.lower()
        if raw.endswith(".8-5-1") or ".8-5-" in raw or raw.startswith("8-5-"):
            product_profile_refs.append(canonical)
        if raw.endswith(".8-4-1") or ".8-4-" in raw or raw.startswith("8-4-"):
            invoice_log_refs.append(canonical)
    return {
        "all_refs": all_refs,
        "product_profile_refs": product_profile_refs,
        "invoice_log_refs": invoice_log_refs,
    }


def select_inherited_ref_for_field(
    *,
    field_id: str,
    field_ref_bindings: dict[str, Any] | None,
) -> str:
    bindings = _to_dict(field_ref_bindings)
    token = _as_text(field_id)
    if token == "inherited_product_profile_ref":
        preferred = [str(item).strip() for item in list(bindings.get("product_profile_refs") or []) if str(item).strip()]
        if preferred:
            return preferred[0]
    if token == "inherited_supply_log_ref":
        preferred = [str(item).strip() for item in list(bindings.get("invoice_log_refs") or []) if str(item).strip()]
        if preferred:
            return preferred[0]
    fallback = [str(item).strip() for item in list(bindings.get("all_refs") or []) if str(item).strip()]
    return fallback[0] if fallback else ""


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
    fallback_refs = []
    for key in ("resource_ref", "target_ref", "inherited_ref"):
        token = _as_text(published_value.get(key))
        if token:
            fallback_refs.append(token)
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
    inherited_resource_ref = select_inherited_ref_for_field(field_id="", field_ref_bindings=bindings)
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
        "provisional_state": provisional_state,
        "context_source": _as_text(context_source) or "published_resource",
    }
