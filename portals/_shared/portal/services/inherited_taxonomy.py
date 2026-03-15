from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple

from ..datum_refs import ParsedDatumRef, normalize_datum_ref, parse_datum_ref
from ..mss.core import preview_mss_context, resolve_contract_datum_ref


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


@dataclass(frozen=True)
class TaxonomyNode:
    identifier: str
    label: str
    pairs: List[Dict[str, str]]
    children: List[str]


_IDENT_RE = re.compile(r"^[0-9]+-[0-9]+-[0-9]+$")


def _parse_identifier(identifier: str) -> Tuple[int, int, int] | None:
    token = _as_text(identifier)
    if not _IDENT_RE.fullmatch(token):
        return None
    layer_s, value_group_s, iteration_s = token.split("-", 2)
    try:
        return int(layer_s), int(value_group_s), int(iteration_s)
    except Exception:
        return None


def _pairs_from_row(row: Dict[str, Any]) -> List[Dict[str, str]]:
    raw_pairs = row.get("pairs") if isinstance(row.get("pairs"), list) else []
    out: List[Dict[str, str]] = []
    for pair in raw_pairs:
        if not isinstance(pair, dict):
            continue
        out.append(
            {
                "reference": _as_text(pair.get("reference")),
                "magnitude": _as_text(pair.get("magnitude")),
            }
        )
    if out:
        return out
    ref = _as_text(row.get("reference"))
    mag = _as_text(row.get("magnitude"))
    if ref or mag:
        return [{"reference": ref, "magnitude": mag}]
    return []


def _split_path(path_token: str) -> List[str]:
    token = _as_text(path_token)
    if not token:
        return []
    return [part for part in token.split("-") if part]


def _path_key(parts: List[str]) -> str:
    if not parts:
        return ""
    return "-".join(parts)


def _rows_to_adjacency(rows: List[Dict[str, Any]]) -> Dict[str, TaxonomyNode]:
    """
    Build a simple parent→children adjacency map from MSS/anthology-style rows.

    Each row's `pairs[].reference` is treated as a parent identifier; rows that
    reference a given identifier become that identifier's children. This is a
    generic mediation that works for taxonomy-like graphs where rows reference
    their logical parents or grouping keys.
    """
    by_id: Dict[str, Dict[str, Any]] = {}
    children_by_parent: Dict[str, List[str]] = {}

    for row in rows or []:
        identifier = _as_text(row.get("identifier") or row.get("row_id"))
        if not identifier:
            continue
        by_id[identifier] = row

    for row in rows or []:
        child_id = _as_text(row.get("identifier") or row.get("row_id"))
        if not child_id:
            continue
        raw_pairs = row.get("pairs") if isinstance(row.get("pairs"), list) else []
        for pair in raw_pairs:
            if not isinstance(pair, dict):
                continue
            parent_id = _as_text(pair.get("reference"))
            if not parent_id:
                continue
            children_by_parent.setdefault(parent_id, []).append(child_id)

    adjacency: Dict[str, TaxonomyNode] = {}
    for identifier, row in by_id.items():
        label = _as_text(row.get("label"))
        raw_pairs = row.get("pairs") if isinstance(row.get("pairs"), list) else []
        pairs: List[Dict[str, str]] = []
        for pair in raw_pairs:
            if not isinstance(pair, dict):
                continue
            pairs.append(
                {
                    "reference": _as_text(pair.get("reference")),
                    "magnitude": _as_text(pair.get("magnitude")),
                }
            )
        adjacency[identifier] = TaxonomyNode(
            identifier=identifier,
            label=label,
            pairs=pairs,
            children=children_by_parent.get(identifier, []),
        )
    return adjacency


def _build_txa_hierarchy_from_collection(
    rows: List[Dict[str, Any]],
    *,
    preferred_collection_id: str = "",
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]] | None:
    """
    Build a hierarchy view from a decompiled MSS collection row.

    MSS decoding intentionally omits labels/icons today. This view derives parent
    relationships from txa-style magnitude paths (e.g. 1-1-2-4 -> parent 1-1-2).
    """
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        identifier = _as_text(row.get("identifier") or row.get("row_id"))
        if identifier:
            by_id[identifier] = row

    if not by_id:
        return None

    candidates: List[Tuple[int, str, List[str]]] = []
    for identifier, row in by_id.items():
        parsed = _parse_identifier(identifier)
        if parsed is None or parsed[1] != 0:
            continue
        ref_ids = [pair.get("reference") or "" for pair in _pairs_from_row(row) if _as_text(pair.get("reference"))]
        score = 0
        for ref_id in ref_ids:
            child = by_id.get(ref_id)
            if not isinstance(child, dict):
                continue
            child_pairs = _pairs_from_row(child)
            if not child_pairs:
                continue
            magnitude = _as_text(child_pairs[0].get("magnitude"))
            if _split_path(magnitude):
                score += 1
        if score > 0:
            candidates.append((score, identifier, ref_ids))

    if not candidates:
        return None

    preferred = _as_text(preferred_collection_id)
    selected_collection = ""
    selected_refs: List[str] = []
    if preferred:
        for _score, cand_id, ref_ids in candidates:
            if cand_id == preferred:
                selected_collection = cand_id
                selected_refs = list(ref_ids)
                break
    if not selected_collection:
        candidates.sort(key=lambda item: (-item[0], item[1]))
        selected_collection = candidates[0][1]
        selected_refs = list(candidates[0][2])

    selected_refs = [item for item in selected_refs if item in by_id]
    if not selected_refs:
        return None

    path_to_id: Dict[str, str] = {}
    node_meta: Dict[str, Dict[str, Any]] = {}
    for ref_id in selected_refs:
        row = by_id.get(ref_id) or {}
        pairs = _pairs_from_row(row)
        magnitude = _as_text(pairs[0].get("magnitude")) if pairs else ""
        path_parts = _split_path(magnitude)
        path_key = _path_key(path_parts)
        if path_key and path_key not in path_to_id:
            path_to_id[path_key] = ref_id
        node_meta[ref_id] = {
            "id": ref_id,
            "label": _as_text(row.get("label")) or ref_id,
            "path": magnitude,
            "pairs": pairs,
            "children": [],
        }

    roots: List[str] = []
    for ref_id in selected_refs:
        item = node_meta.get(ref_id) or {}
        path_parts = _split_path(_as_text(item.get("path")))
        parent_id = ""
        if len(path_parts) > 1:
            parent_key = _path_key(path_parts[:-1])
            parent_id = _as_text(path_to_id.get(parent_key))
        if parent_id and parent_id in node_meta:
            node_meta[parent_id]["children"].append(ref_id)
        else:
            roots.append(ref_id)

    for meta in node_meta.values():
        children = list(dict.fromkeys(meta.get("children") or []))
        children.sort()
        meta["children"] = children
    roots = sorted(list(dict.fromkeys(roots)))

    def _build(node_id: str) -> Dict[str, Any]:
        meta = node_meta.get(node_id)
        if not isinstance(meta, dict):
            return {"id": node_id, "label": node_id, "path": "", "children": []}
        return {
            "id": _as_text(meta.get("id")),
            "label": _as_text(meta.get("label")),
            "path": _as_text(meta.get("path")),
            "children": [_build(child_id) for child_id in list(meta.get("children") or [])],
        }

    tree = {
        "id": selected_collection,
        "label": _as_text((by_id.get(selected_collection) or {}).get("label")) or selected_collection,
        "path": "",
        "children": [_build(root_id) for root_id in roots],
    }
    nodes = [dict(value) for value in node_meta.values()]
    return selected_collection, nodes, tree


def _normalize_ref(datum_ref: str, *, local_msn_id: str) -> ParsedDatumRef:
    parsed = parse_datum_ref(datum_ref, field_name="taxonomy_ref")
    # Ensure we always have a canonical MSN qualifier for network writes.
    canonical = normalize_datum_ref(
        datum_ref,
        local_msn_id=local_msn_id,
        require_qualified=True,
        write_format="dot",
        field_name="taxonomy_ref",
    )
    canonical_parsed = parse_datum_ref(canonical, field_name="taxonomy_ref")
    return canonical_parsed


def _local_taxonomy_context(
    *,
    parsed: ParsedDatumRef,
    local_msn_id: str,
    anthology_payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    For local taxonomy references, compile a minimal MSS payload using the
    anthology and the selected ref closure via preview_mss_context.
    """
    # Use preview_mss_context in compile mode to build a compact closure.
    preview = preview_mss_context(
        anthology_payload=anthology_payload,
        selected_refs=[parsed.datum_address],
        bitstring="",
        local_msn_id=local_msn_id,
    )
    rows = list(preview.get("rows") or [])
    return preview, rows


def _foreign_taxonomy_context(
    *,
    datum_ref: str,
    parsed: ParsedDatumRef,
    local_msn_id: str,
    anthology_payload: Dict[str, Any],
    contract_payloads: List[Dict[str, Any]],
    preferred_contract_id: str = "",
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    For foreign taxonomy references, resolve the datum via contract MSS context
    using resolve_contract_datum_ref. This surfaces both the specific row and
    the decoded MSS payload that defines the inherited anthology slice.
    """
    resolution = resolve_contract_datum_ref(
        datum_ref,
        local_msn_id=local_msn_id,
        anthology_payload=anthology_payload,
        contract_payloads=contract_payloads,
        preferred_contract_id=preferred_contract_id,
    )
    decoded = resolution.get("decoded") if isinstance(resolution.get("decoded"), dict) else {}
    rows = list(decoded.get("rows") or [])
    return resolution, rows


def load_inherited_taxonomy(
    *,
    datum_ref: str,
    local_msn_id: str,
    anthology_payload: Optional[Dict[str, Any]] = None,
    contract_payloads: Optional[List[Dict[str, Any]]] = None,
    preferred_contract_id: str = "",
) -> Dict[str, Any]:
    """
    Resolve a taxonomy collection datum reference into a normalized tree
    structure suitable for portal tools.

    - Accepts any supported datum_ref syntax and normalizes it to canonical
      dot-qualified form for use in network and request-log events.
    - For local references (no msn_id or msn_id == local_msn_id), compiles a
      compact MSS closure from the local anthology and builds a tree.
    - For foreign references (msn_id != local_msn_id), uses contract MSS
      decoding via resolve_contract_datum_ref and builds a tree from the
      decoded rows.

    Returns a payload with:
    - ok: bool
    - reason: optional error string when ok is False
    - taxonomy_ref: canonical dot-qualified token
    - root_identifier: identifier within the decoded rows matching the datum
    - nodes: flat list of {id, label, pairs, children}
    - tree: nested {id, label, children:[...]} form for convenience
    - scope: "local" or "contract_mss"
    - raw_context: minimal raw context from MSS/contract resolution
    """
    local_msn_id = _as_text(local_msn_id)
    if not local_msn_id:
        return {
            "ok": False,
            "reason": "local_msn_id is required",
            "taxonomy_ref": _as_text(datum_ref),
        }

    try:
        canonical_parsed = _normalize_ref(datum_ref, local_msn_id=local_msn_id)
    except Exception as exc:
        return {
            "ok": False,
            "reason": f"Invalid taxonomy datum_ref: {exc}",
            "taxonomy_ref": _as_text(datum_ref),
        }

    canonical_ref = canonical_parsed.canonical_dot
    anthology_payload = dict(anthology_payload or {})
    contract_payloads = list(contract_payloads or [])

    if not canonical_parsed.msn_id or canonical_parsed.msn_id == local_msn_id:
        scope = "local"
        context, rows = _local_taxonomy_context(
            parsed=canonical_parsed,
            local_msn_id=local_msn_id,
            anthology_payload=anthology_payload,
        )
    else:
        scope = "contract_mss"
        if not contract_payloads:
            return {
                "ok": False,
                "reason": "No contract_payloads provided for foreign taxonomy reference",
                "taxonomy_ref": canonical_ref,
                "scope": scope,
            }
        context, rows = _foreign_taxonomy_context(
            datum_ref=canonical_ref,
            parsed=canonical_parsed,
            local_msn_id=local_msn_id,
            anthology_payload=anthology_payload,
            contract_payloads=contract_payloads,
            preferred_contract_id=preferred_contract_id,
        )

    if not rows:
        return {
            "ok": False,
            "reason": "No rows available for taxonomy context",
            "taxonomy_ref": canonical_ref,
            "scope": scope,
            "raw_context": context,
        }

    root_identifier = canonical_parsed.datum_address
    has_root = any(
        _as_text(row.get("identifier") or row.get("row_id")) == root_identifier for row in rows
    )
    if not has_root:
        # Fall back to last row as root if the requested identifier is not present.
        fallback_identifier = _as_text(rows[-1].get("identifier") or rows[-1].get("row_id"))
        root_identifier = fallback_identifier or root_identifier

    hierarchy = _build_txa_hierarchy_from_collection(rows, preferred_collection_id=root_identifier)
    if hierarchy is not None:
        root_identifier, nodes, tree = hierarchy
    else:
        adjacency = _rows_to_adjacency(rows)

        def _build_tree(node_id: str) -> Dict[str, Any]:
            node = adjacency.get(node_id)
            if node is None:
                return {"id": node_id, "label": "", "path": "", "children": []}
            return {
                "id": node.identifier,
                "label": node.label,
                "path": "",
                "children": [_build_tree(child_id) for child_id in node.children],
            }

        tree = _build_tree(root_identifier)
        nodes = [
            {
                "id": node.identifier,
                "label": node.label,
                "path": "",
                "pairs": list(node.pairs),
                "children": list(node.children),
            }
            for node in adjacency.values()
        ]

    return {
        "ok": True,
        "taxonomy_ref": canonical_ref,
        "scope": scope,
        "root_identifier": root_identifier,
        "nodes": nodes,
        "tree": tree,
        "raw_context": {
            "rows_count": len(rows),
            "context": context,
        },
    }

