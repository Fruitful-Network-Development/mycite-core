from __future__ import annotations

import hashlib
import re
from typing import Any


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


_DATUM_ID_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def _is_samras_hint(text: str) -> bool:
    token = text.lower()
    return "samras" in token


def _infer_role(label_text: str) -> str:
    token = label_text.lower()
    if "space" in token:
        return "space"
    if "field" in token:
        return "field"
    if "babelette" in token or "id" in token or "value" in token:
        return "value"
    return "definer"


def _infer_value_kind(text: str) -> str:
    token = text.lower()
    if "txa" in token:
        return "txa_id"
    if "msn" in token:
        return "msn_id"
    return "address_id"


def _normalized_summary(raw: str) -> dict[str, Any]:
    token = _as_text(raw)
    hyphen_parts = [item for item in token.split("-") if item != ""]
    comma_parts = [item for item in token.split(",") if item != ""]
    numeric_parts = [item for item in hyphen_parts if item.isdigit()]
    return {
        "raw_length": len(token),
        "hyphen_segment_count": len(hyphen_parts),
        "comma_section_count": max(1, len(comma_parts)) if token else 0,
        "numeric_segment_count": len(numeric_parts),
        "contains_alpha": any(ch.isalpha() for ch in token),
        "contains_json_like": ("{" in token and "}" in token) or ("[" in token and "]" in token),
    }


def _provisional_state(summary: dict[str, Any]) -> str:
    if not summary:
        return "unknown"
    if bool(summary.get("contains_alpha")) or int(summary.get("comma_section_count") or 0) > 1:
        return "provisional_noncanonical"
    return "provisional_numeric_hyphen"


def compile_provisional_samras_descriptor(
    *,
    source_datum_id: str,
    label: str,
    magnitude: str,
    context_source: str,
    source_scope: str,
) -> dict[str, Any]:
    seed = f"{_as_text(source_datum_id)}|{_as_text(label)}|{_as_text(magnitude)}|{_as_text(context_source)}"
    descriptor_digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    summary = _normalized_summary(_as_text(magnitude))
    text = f"{_as_text(label)} {_as_text(magnitude)}"
    return {
        "constraint_family": "samras",
        "descriptor_digest": descriptor_digest,
        "role": _infer_role(text),
        "value_kind": _infer_value_kind(text),
        "context_source": _as_text(context_source) or "merged_graph",
        "provisional_state": _provisional_state(summary),
        "source_datum_id": _as_text(source_datum_id),
        "source_scope": _as_text(source_scope) or "portal",
        "normalized_structure_summary": summary,
    }


def compile_samras_descriptors_from_rows(
    rows_by_id: dict[str, dict[str, Any]],
    *,
    context_source: str = "merged_graph",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for datum_id, row in dict(rows_by_id or {}).items():
        token = _as_text(datum_id)
        if _DATUM_ID_RE.fullmatch(token) is None:
            continue
        label = _as_text((row or {}).get("label"))
        magnitude = _as_text((row or {}).get("magnitude"))
        if not _is_samras_hint(f"{label} {magnitude}"):
            continue
        out.append(
            compile_provisional_samras_descriptor(
                source_datum_id=token,
                label=label,
                magnitude=magnitude,
                context_source=context_source,
                source_scope=_as_text((row or {}).get("source_scope") or "portal"),
            )
        )
    out.sort(key=lambda item: _as_text(item.get("source_datum_id")))
    return out


def compile_samras_constraint_for_chain(
    *,
    chain: list[dict[str, Any]],
    rows_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not chain:
        return {}
    # Prefer explicit SAMRAS row in chain; fall back to merged row scan.
    for node in chain:
        source_datum_id = _as_text(node.get("identifier"))
        label = _as_text(node.get("label"))
        magnitude = _as_text(node.get("magnitude"))
        if _is_samras_hint(f"{label} {magnitude}"):
            source_row = rows_by_id.get(source_datum_id) if isinstance(rows_by_id, dict) else {}
            return compile_provisional_samras_descriptor(
                source_datum_id=source_datum_id,
                label=label,
                magnitude=magnitude,
                context_source="aitas.chain",
                source_scope=_as_text((source_row or {}).get("source_scope") or "portal"),
            )

    descriptors = compile_samras_descriptors_from_rows(rows_by_id, context_source="aitas.graph_scan")
    if not descriptors:
        return {}
    # Prefer txa_id descriptor when available for inherited write-oriented flows.
    for item in descriptors:
        if _as_text(item.get("value_kind")) == "txa_id":
            return item
    return descriptors[0]
