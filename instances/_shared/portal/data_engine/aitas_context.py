from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable

from ..datum_refs import normalize_datum_ref, parse_datum_ref
from .archetypes import ArchetypeDefinition, get_archetype_definition, list_archetype_definitions
from .datum_identity import resolve_to_local_row
from .inherited_txa_adapter import adapt_published_txa_resource_value
from .samras_descriptor_compiler import compile_samras_constraint_for_chain


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _extract_rows(anthology_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = anthology_payload.get("rows") if isinstance(anthology_payload, dict) else []
    if isinstance(rows, dict):
        out: list[dict[str, Any]] = []
        for key, value in rows.items():
            if isinstance(value, dict):
                item = dict(value)
            else:
                item = {}
            item.setdefault("identifier", _as_text(item.get("identifier") or item.get("row_id") or key))
            out.append(item)
        return out
    if isinstance(rows, list):
        return [dict(item) for item in rows if isinstance(item, dict)]
    return []


def _row_identifier(row: dict[str, Any]) -> str:
    return _as_text(row.get("identifier") or row.get("row_id"))


def _pairs_for_row(row: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    pairs = row.get("pairs")
    if isinstance(pairs, list):
        for item in pairs:
            if not isinstance(item, dict):
                continue
            out.append({"reference": _as_text(item.get("reference")), "magnitude": _as_text(item.get("magnitude"))})
        return out
    reference = _as_text(row.get("reference"))
    magnitude = _as_text(row.get("magnitude"))
    if reference or magnitude:
        out.append({"reference": reference, "magnitude": magnitude})
    return out


def _is_identifier(token: str) -> bool:
    parts = token.split("-")
    return len(parts) == 3 and all(part.isdigit() for part in parts)


def _build_rows_by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_row_identifier(row): row for row in rows if _row_identifier(row)}


def _build_chain(rows_by_id: dict[str, dict[str, Any]], start_id: str, *, max_depth: int = 16) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    cursor = _as_text(start_id)
    depth = 0
    while cursor and cursor not in seen and depth < max_depth:
        row = rows_by_id.get(cursor)
        if not isinstance(row, dict):
            break
        seen.add(cursor)
        pairs = _pairs_for_row(row)
        chain.append(
            {
                "identifier": cursor,
                "label": _as_text(row.get("label")),
                "source_identifier": _as_text(row.get("source_identifier")),
                "pairs": pairs,
                "magnitude": _as_text(row.get("magnitude")),
            }
        )
        next_cursor = ""
        for pair in pairs:
            candidate = _as_text(pair.get("reference"))
            if _is_identifier(candidate):
                next_cursor = candidate
                break
        cursor = next_cursor
        depth += 1
    return chain


def _chain_signature(chain: list[dict[str, Any]]) -> str:
    raw = " > ".join(_as_text(item.get("identifier")) for item in chain)
    if not raw:
        return ""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _int_from_payload(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        raw = payload.get(key)
        if raw is None:
            continue
        try:
            return int(str(raw).strip())
        except Exception:
            continue
    return None


def _compile_constraint_summary(
    row: dict[str, Any],
    chain: list[dict[str, Any]],
    *,
    rows_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    constraints: dict[str, Any] = {
        "field_length": None,
        "alphabet_cardinality": None,
        "evidence": [],
    }
    magnitude = _as_text(row.get("magnitude"))
    if magnitude:
        try:
            payload = json.loads(magnitude)
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            field_length = _int_from_payload(payload, "field_length", "length", "max_length")
            alphabet_cardinality = _int_from_payload(payload, "alphabet_cardinality", "cardinality", "alphabet_size")
            if field_length is not None:
                constraints["field_length"] = field_length
                constraints["evidence"].append("magnitude.field_length")
            if alphabet_cardinality is not None:
                constraints["alphabet_cardinality"] = alphabet_cardinality
                constraints["evidence"].append("magnitude.alphabet_cardinality")
            inherited_payload = payload.get("inherited_context")
            if isinstance(inherited_payload, dict):
                adapted = adapt_published_txa_resource_value(
                    payload=inherited_payload,
                    context_source="aitas.compiled_constraint.inherited_context",
                )
                if adapted.get("ok"):
                    constraints["inherited_resource_ref"] = _as_text(adapted.get("inherited_resource_ref"))
                    constraints["constraint_family"] = _as_text(adapted.get("constraint_family") or "samras")
                    constraints["descriptor_digest"] = _as_text(adapted.get("descriptor_digest"))
                    constraints["value_kind"] = _as_text(adapted.get("value_kind") or "txa_id")
                    constraints["role"] = _as_text(adapted.get("role") or "value")
                    constraints["context_source"] = _as_text(adapted.get("context_source"))
                    constraints["provisional_state"] = _as_text(adapted.get("provisional_state"))
                    constraints["evidence"].append("inherited_txa_adapter")
    if constraints["field_length"] is None or constraints["alphabet_cardinality"] is None:
        chain_text = " ".join(
            _as_text(item.get("label")) + " " + _as_text(item.get("magnitude")) + " " + _as_text(item.get("identifier"))
            for item in chain
        ).lower()
        if constraints["field_length"] is None and "64" in chain_text:
            constraints["field_length"] = 64
            constraints["evidence"].append("chain_text.64")
        if constraints["alphabet_cardinality"] is None and ("256" in chain_text or "ascii" in chain_text):
            constraints["alphabet_cardinality"] = 256
            constraints["evidence"].append("chain_text.256_or_ascii")
    samras_constraint = compile_samras_constraint_for_chain(
        chain=chain,
        rows_by_id=rows_by_id if isinstance(rows_by_id, dict) else {},
    )
    if samras_constraint:
        constraints["samras"] = dict(samras_constraint)
        constraints.setdefault("constraint_family", _as_text(samras_constraint.get("constraint_family") or "samras"))
        constraints.setdefault("descriptor_digest", _as_text(samras_constraint.get("descriptor_digest")))
        constraints.setdefault("value_kind", _as_text(samras_constraint.get("value_kind")))
        constraints.setdefault("role", _as_text(samras_constraint.get("role")))
        constraints.setdefault("context_source", _as_text(samras_constraint.get("context_source")))
        constraints.setdefault("provisional_state", _as_text(samras_constraint.get("provisional_state")))
        constraints["evidence"].append("samras_descriptor_compiler")
    return constraints


def _match_definition(
    definition: ArchetypeDefinition,
    *,
    chain: list[dict[str, Any]],
    compiled_constraint: dict[str, Any],
) -> tuple[bool, float, list[str]]:
    chain_text = " ".join(
        f"{_as_text(item.get('identifier'))} {_as_text(item.get('label'))} {_as_text(item.get('magnitude'))}"
        for item in chain
    ).lower()
    reasons: list[str] = []
    chain_ok = all(marker.lower() in chain_text for marker in definition.chain_pattern)
    if chain_ok:
        reasons.append("chain_pattern matched")
    expectation = definition.constraint_expectation
    expected_length = int(expectation.get("field_length"))
    expected_cardinality = int(expectation.get("alphabet_cardinality"))
    constraint_ok = (
        int(compiled_constraint.get("field_length") or -1) == expected_length
        and int(compiled_constraint.get("alphabet_cardinality") or -1) == expected_cardinality
    )
    if constraint_ok:
        reasons.append("constraint_expectation matched")
    if not chain_ok and not constraint_ok:
        return False, 0.0, reasons
    score = 0.0
    if chain_ok:
        score += 0.45
    if constraint_ok:
        score += 0.55
    return chain_ok and constraint_ok, min(1.0, score), reasons


@dataclass(frozen=True)
class ArchetypeBinding:
    archetype_key: str
    local_ref: str
    canonical_ref: str
    source_identifier: str
    chain_signature: str
    compiled_constraint: dict[str, Any]
    lens_key: str
    closure_hash: str
    closure_form: str
    confidence: float
    derived_at_unix_ms: int
    revision: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "archetype_key": self.archetype_key,
            "local_ref": self.local_ref,
            "canonical_ref": self.canonical_ref,
            "source_identifier": self.source_identifier,
            "chain_signature": self.chain_signature,
            "compiled_constraint": dict(self.compiled_constraint),
            "lens_key": self.lens_key,
            "closure_hash": self.closure_hash,
            "closure_form": self.closure_form,
            "confidence": self.confidence,
            "derived_at_unix_ms": self.derived_at_unix_ms,
            "revision": self.revision,
        }


def _build_binding(
    definition: ArchetypeDefinition,
    *,
    local_ref: str,
    canonical_ref: str,
    source_identifier: str,
    chain: list[dict[str, Any]],
    compiled_constraint: dict[str, Any],
    confidence: float,
    now_fn: Callable[[], int],
) -> ArchetypeBinding:
    signature = _chain_signature(chain)
    closure_hash = hashlib.sha256(
        json.dumps({"signature": signature, "constraint": compiled_constraint}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return ArchetypeBinding(
        archetype_key=definition.archetype_key,
        local_ref=local_ref,
        canonical_ref=canonical_ref,
        source_identifier=source_identifier,
        chain_signature=signature,
        compiled_constraint=dict(compiled_constraint),
        lens_key=definition.lens_key,
        closure_hash=closure_hash,
        closure_form="chain+compiled_constraint",
        confidence=confidence,
        derived_at_unix_ms=now_fn(),
        revision=1,
    )


def inspect_archetype_context(
    *,
    datum_ref: str,
    local_msn_id: str,
    anthology_payload: dict[str, Any],
    now_fn: Callable[[], int] | None = None,
) -> dict[str, Any]:
    now = now_fn or (lambda: int(time.time()))
    local_msn = _as_text(local_msn_id)
    if not local_msn:
        return {"ok": False, "error": "local_msn_id is required"}
    canonical_ref = normalize_datum_ref(datum_ref, local_msn_id=local_msn, write_format="dot", field_name="datum_ref")
    parsed = parse_datum_ref(canonical_ref, field_name="datum_ref")
    rows = _extract_rows(anthology_payload if isinstance(anthology_payload, dict) else {})
    resolution = resolve_to_local_row(canonical_ref, anthology_rows=rows, local_msn_id=local_msn)
    if not resolution.ok:
        return {
            "ok": False,
            "datum_ref": datum_ref,
            "canonical_ref": canonical_ref,
            "error": resolution.reason or "datum not found in anthology",
        }
    row = dict(resolution.row)
    rows_by_id = _build_rows_by_id(rows)
    chain = _build_chain(rows_by_id, _as_text(resolution.storage_address or parsed.datum_address))
    compiled_constraint = _compile_constraint_summary(row, chain, rows_by_id=rows_by_id)
    definition_matches: list[dict[str, Any]] = []
    binding_payload: dict[str, Any] = {}
    for definition in list_archetype_definitions():
        matched, confidence, reasons = _match_definition(definition, chain=chain, compiled_constraint=compiled_constraint)
        item = {
            "archetype_key": definition.archetype_key,
            "matched": matched,
            "confidence": confidence,
            "reasons": reasons,
        }
        definition_matches.append(item)
        if matched and not binding_payload:
            binding = _build_binding(
                definition,
                local_ref=parsed.datum_address,
                canonical_ref=canonical_ref,
                source_identifier=_as_text(row.get("source_identifier")),
                chain=chain,
                compiled_constraint=compiled_constraint,
                confidence=confidence,
                now_fn=now,
            )
            binding_payload = binding.to_dict()
    return {
        "ok": True,
        "datum_ref": datum_ref,
        "local_ref": parsed.datum_address,
        "canonical_ref": canonical_ref,
        "aitas": {
            "attention": {},
            "intention": {},
            "time": {},
            "archetype": {
                "recognized": bool(binding_payload),
                "binding": binding_payload,
                "definition_matches": definition_matches,
                "compiled_constraint": compiled_constraint,
            },
            "space": {},
        },
        "lens_context": {
            "lens_key": _as_text(binding_payload.get("lens_key")),
            "archetype_key": _as_text(binding_payload.get("archetype_key")),
        },
        "chain_signature": _chain_signature(chain),
        "chain": chain,
    }


def inspect_archetype_trace(
    *,
    datum_ref: str,
    local_msn_id: str,
    anthology_payload: dict[str, Any],
) -> dict[str, Any]:
    inspected = inspect_archetype_context(
        datum_ref=datum_ref,
        local_msn_id=local_msn_id,
        anthology_payload=anthology_payload,
    )
    if not inspected.get("ok"):
        return inspected
    chain = list(inspected.get("chain") or [])
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for item in chain:
        identifier = _as_text(item.get("identifier"))
        nodes.append(
            {
                "id": identifier,
                "label": _as_text(item.get("label")) or identifier,
                "kind": "datum",
                "source_identifier": _as_text(item.get("source_identifier")),
            }
        )
        for pair in list(item.get("pairs") or []):
            ref = _as_text((pair or {}).get("reference"))
            if ref and _is_identifier(ref):
                edges.append({"from": identifier, "to": ref, "kind": "inherits"})
    binding = (((inspected.get("aitas") or {}).get("archetype") or {}).get("binding") or {})
    archetype_key = _as_text(binding.get("archetype_key"))
    if archetype_key:
        aid = f"archetype:{archetype_key}"
        nodes.append({"id": aid, "label": archetype_key, "kind": "archetype"})
        if chain:
            edges.append({"from": _as_text(chain[0].get("identifier")), "to": aid, "kind": "recognized_as"})
    return {
        "ok": True,
        "datum_ref": inspected.get("datum_ref"),
        "local_ref": inspected.get("local_ref"),
        "canonical_ref": inspected.get("canonical_ref"),
        "recognized_archetype": archetype_key,
        "compiled_constraint": (((inspected.get("aitas") or {}).get("archetype") or {}).get("compiled_constraint") or {}),
        "trace": {"nodes": nodes, "edges": edges, "chain": chain},
        "lens_context": dict(inspected.get("lens_context") or {}),
    }


def list_derived_archetype_bindings(
    *,
    local_msn_id: str,
    anthology_payload: dict[str, Any],
    limit: int = 200,
) -> dict[str, Any]:
    local_msn = _as_text(local_msn_id)
    rows = _extract_rows(anthology_payload if isinstance(anthology_payload, dict) else {})
    out: list[dict[str, Any]] = []
    for row in rows:
        if len(out) >= max(1, int(limit or 200)):
            break
        rid = _row_identifier(row)
        if not rid:
            continue
        inspected = inspect_archetype_context(
            datum_ref=rid,
            local_msn_id=local_msn,
            anthology_payload=anthology_payload,
        )
        binding = ((((inspected.get("aitas") or {}).get("archetype") or {}).get("binding")) or {})
        if binding:
            out.append(dict(binding))
    return {"ok": True, "bindings": out, "count": len(out)}


def list_archetype_registry_payload() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": "mycite.portal.aitas.archetypes.v1",
        "definitions": [item.to_dict() for item in list_archetype_definitions()],
    }


def get_archetype_definition_payload(archetype_key: str) -> dict[str, Any]:
    definition = get_archetype_definition(archetype_key)
    if definition is None:
        return {"ok": False, "error": f"unknown archetype_key: {archetype_key}"}
    return {"ok": True, "definition": definition.to_dict()}
