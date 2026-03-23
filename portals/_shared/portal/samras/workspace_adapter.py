from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from _shared.portal.data_contract import compact_payload_to_rows
from _shared.portal.data_contract.anthology_pairs import compact_row_to_record

from .codec import decode_structure, encode_canonical_structure_from_addresses
from .mutation import SamrasMutationResult, add_child, add_root, move_branch, remove_branch, set_child_count
from .structure import SamrasStructure, address_depth, address_sort_key, as_text, parent_address, parse_address_segments
from .validation import InvalidSamrasStructure


def _looks_like_binary(token: str) -> bool:
    return bool(token) and all(ch in {"0", "1"} for ch in token)


def _looks_like_address(token: str) -> bool:
    raw = as_text(token)
    if not raw:
        return False
    if "-" not in raw:
        return raw.isdigit() and raw != "0" and len(raw) <= 6
    parts = raw.split("-")
    return bool(parts) and all(part.isdigit() and part != "0" for part in parts)


def _raw_base(raw_value: object) -> list[str]:
    row_values = raw_value if isinstance(raw_value, list) else []
    base = row_values[0] if len(row_values) > 0 and isinstance(row_values[0], list) else []
    return [str(item).strip() for item in base]


def _raw_labels(raw_value: object) -> list[str]:
    row_values = raw_value if isinstance(raw_value, list) else []
    labels = row_values[1] if len(row_values) > 1 and isinstance(row_values[1], list) else []
    return [str(item).strip() for item in labels if str(item).strip()]


@dataclass(frozen=True)
class SamrasWorkspaceNode:
    address_id: str
    title: str
    titles: tuple[str, ...]
    parent_address: str
    depth: int
    child_count: int
    child_addresses: tuple[str, ...]
    row_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "address_id": self.address_id,
            "title": self.title,
            "titles": [str(item) for item in self.titles],
            "parent_address": self.parent_address,
            "depth": int(self.depth),
            "child_count": int(self.child_count),
            "child_addresses": [str(item) for item in self.child_addresses],
            "row_ids": [str(item) for item in self.row_ids],
        }


@dataclass(frozen=True)
class SamrasWorkspaceResource:
    structure_row_id: str
    structure_label: str
    structure: SamrasStructure
    nodes: tuple[SamrasWorkspaceNode, ...]
    title_reference: str
    title_layer: int
    title_value_group: int
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "structure_row_id": self.structure_row_id,
            "structure_label": self.structure_label,
            "structure": self.structure.to_dict(),
            "nodes": [item.to_dict() for item in self.nodes],
            "title_reference": self.title_reference,
            "title_layer": int(self.title_layer),
            "title_value_group": int(self.title_value_group),
            "warnings": [str(item) for item in self.warnings],
        }


def _select_structure_entry(payload: dict[str, Any]) -> tuple[str, str, str, tuple[str, ...]]:
    best_score = -1
    picked: tuple[str, str, str, tuple[str, ...]] | None = None
    for row_key, raw_value in dict(payload or {}).items():
        base = _raw_base(raw_value)
        labels = tuple(_raw_labels(raw_value))
        label_text = " ".join(labels).lower()
        row_id = as_text(row_key)
        if not row_id:
            continue
        score = -1
        magnitude = ""
        if len(base) >= 3 and as_text(base[1]) == "0-0-5" and (_looks_like_binary(as_text(base[2])) or "-" in as_text(base[2])):
            magnitude = as_text(base[2])
            score = 100
        elif len(base) == 2 and (_looks_like_binary(as_text(base[1])) or "-" in as_text(base[1])):
            magnitude = as_text(base[1])
            score = 50
        if score < 0:
            continue
        if "samras" in label_text or "txa" in label_text or "msn" in label_text:
            score += 10
        if row_id.startswith("1-"):
            score += 5
        if score > best_score:
            picked = (row_id, labels[0] if labels else "", magnitude, labels)
            best_score = score
    if picked is None:
        raise InvalidSamrasStructure("unable to locate a SAMRAS structure row in the payload")
    return picked


def _title_rows_by_address(payload: dict[str, Any], valid_addresses: set[str]) -> tuple[dict[str, list[dict[str, Any]]], str, int, int]:
    rows = compact_payload_to_rows(payload if isinstance(payload, dict) else {}, strict=False)
    grouped: dict[str, list[dict[str, Any]]] = {}
    refs: list[str] = []
    layers: list[int] = []
    value_groups: list[int] = []
    for row in rows:
        magnitude = as_text(row.get("magnitude"))
        if magnitude not in valid_addresses:
            continue
        grouped.setdefault(magnitude, []).append(dict(row))
        reference = as_text(row.get("reference"))
        if reference:
            refs.append(reference)
        identifier = as_text(row.get("row_id") or row.get("identifier"))
        parts = identifier.split("-")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            layers.append(int(parts[0], 10))
            value_groups.append(int(parts[1], 10))
    ref_counter = Counter(refs)
    layer_counter = Counter(layers)
    group_counter = Counter(value_groups)
    return (
        grouped,
        ref_counter.most_common(1)[0][0] if ref_counter else "",
        layer_counter.most_common(1)[0][0] if layer_counter else 4,
        group_counter.most_common(1)[0][0] if group_counter else 1,
    )


def _address_fallback_rows(payload: dict[str, Any]) -> list[str]:
    rows = compact_payload_to_rows(payload if isinstance(payload, dict) else {}, strict=False)
    raw_addresses = {as_text(row.get("magnitude")) for row in rows if _looks_like_address(as_text(row.get("magnitude")))}
    expanded: set[str] = set(raw_addresses)
    changed = True
    while changed:
        changed = False
        snapshot = sorted(expanded, key=address_sort_key)
        for address in snapshot:
            parent = parent_address(address)
            while parent:
                if parent not in expanded:
                    expanded.add(parent)
                    changed = True
                parent = parent_address(parent)
        parent_to_ordinals: dict[str, set[int]] = {}
        for address in list(expanded):
            segments = parse_address_segments(address)
            parent = "-".join(str(item) for item in segments[:-1]) if len(segments) > 1 else ""
            parent_to_ordinals.setdefault(parent, set()).add(int(segments[-1]))
        for parent, ordinals in parent_to_ordinals.items():
            maximum = max(ordinals) if ordinals else 0
            for ordinal in range(1, maximum + 1):
                candidate = str(ordinal) if not parent else f"{parent}-{ordinal}"
                if candidate not in expanded:
                    expanded.add(candidate)
                    changed = True
    addresses = sorted(expanded, key=address_sort_key)
    return addresses


def _build_nodes(structure: SamrasStructure, title_rows: dict[str, list[dict[str, Any]]]) -> tuple[SamrasWorkspaceNode, ...]:
    nodes: list[SamrasWorkspaceNode] = []
    child_count_map = structure.address_map
    by_parent: dict[str, list[str]] = {}
    for address in structure.addresses:
        by_parent.setdefault(parent_address(address), []).append(address)
    for children in by_parent.values():
        children.sort(key=address_sort_key)
    for address in structure.addresses:
        rows = list(title_rows.get(address, ()))
        titles = tuple(as_text(item.get("label")) for item in rows if as_text(item.get("label")))
        row_ids = tuple(as_text(item.get("row_id") or item.get("identifier")) for item in rows if as_text(item.get("row_id") or item.get("identifier")))
        nodes.append(
            SamrasWorkspaceNode(
                address_id=address,
                title=titles[0] if titles else "",
                titles=titles,
                parent_address=parent_address(address),
                depth=address_depth(address),
                child_count=int(child_count_map.get(address) or 0),
                child_addresses=tuple(by_parent.get(address, ())),
                row_ids=row_ids,
            )
        )
    return tuple(nodes)


def load_workspace_from_compact_payload(payload: dict[str, Any]) -> SamrasWorkspaceResource:
    structure_row_id, structure_label, magnitude, _labels = _select_structure_entry(payload)
    structure_warnings: list[str] = []
    try:
        structure = decode_structure(magnitude, root_ref="0-0-5")
    except Exception as exc:
        fallback_addresses = _address_fallback_rows(payload)
        if not fallback_addresses:
            raise
        structure = encode_canonical_structure_from_addresses(fallback_addresses, root_ref="0-0-5")
        structure_warnings.append(
            "structure row could not be decoded; canonical SAMRAS structure was reconstructed from staged address rows"
        )
        structure_warnings.append(str(exc))
    title_rows, title_reference, title_layer, title_value_group = _title_rows_by_address(payload, set(structure.addresses))
    nodes = _build_nodes(structure, title_rows)
    warnings = list(structure.warnings) + structure_warnings
    if not title_reference:
        warnings.append("no dominant title reference could be inferred; new title rows will use an empty reference")
    return SamrasWorkspaceResource(
        structure_row_id=structure_row_id,
        structure_label=structure_label,
        structure=structure,
        nodes=nodes,
        title_reference=title_reference,
        title_layer=title_layer,
        title_value_group=title_value_group,
        warnings=tuple(warnings),
    )


def load_workspace_from_resource_body(resource_body: dict[str, Any]) -> SamrasWorkspaceResource:
    anthology_payload = (
        resource_body.get("anthology_compatible_payload")
        if isinstance(resource_body.get("anthology_compatible_payload"), dict)
        else {}
    )
    if anthology_payload:
        try:
            workspace = load_workspace_from_compact_payload(anthology_payload)
            return SamrasWorkspaceResource(
                structure_row_id=workspace.structure_row_id,
                structure_label=workspace.structure_label,
                structure=workspace.structure,
                nodes=workspace.nodes,
                title_reference=workspace.title_reference,
                title_layer=workspace.title_layer,
                title_value_group=workspace.title_value_group,
                warnings=workspace.warnings
                + ("resource workspace was loaded from anthology_compatible_payload",),
            )
        except InvalidSamrasStructure:
            pass

    canonical_state = resource_body.get("canonical_state") if isinstance(resource_body.get("canonical_state"), dict) else {}
    compact_payload = canonical_state.get("compact_payload") if isinstance(canonical_state.get("compact_payload"), dict) else {}
    if compact_payload:
        try:
            workspace = load_workspace_from_compact_payload(compact_payload)
            return SamrasWorkspaceResource(
                structure_row_id=workspace.structure_row_id,
                structure_label=workspace.structure_label,
                structure=workspace.structure,
                nodes=workspace.nodes,
                title_reference=workspace.title_reference,
                title_layer=workspace.title_layer,
                title_value_group=workspace.title_value_group,
                warnings=workspace.warnings + ("resource workspace was loaded from canonical_state.compact_payload",),
            )
        except InvalidSamrasStructure:
            pass

    structure_payload = as_text(resource_body.get("structure_payload") or resource_body.get("canonical_magnitude") or resource_body.get("legacy_structure_payload_input"))
    warnings: list[str] = []
    structure: SamrasStructure
    if structure_payload:
        structure = decode_structure(structure_payload, root_ref=as_text(resource_body.get("root_ref")) or "0-0-5")
    else:
        rows_by_address = resource_body.get("rows_by_address") if isinstance(resource_body.get("rows_by_address"), dict) else {}
        address_keys = sorted((as_text(key) for key in rows_by_address.keys() if as_text(key)), key=address_sort_key)
        if not address_keys:
            raise InvalidSamrasStructure("resource body does not carry a SAMRAS structure payload")
        structure = encode_canonical_structure_from_addresses(address_keys, root_ref=as_text(resource_body.get("root_ref")) or "0-0-5")
        warnings.append("resource body lacked structure payload; canonical SAMRAS structure was reconstructed from rows_by_address")

    rows_by_address = resource_body.get("rows_by_address") if isinstance(resource_body.get("rows_by_address"), dict) else {}
    title_rows: dict[str, list[dict[str, Any]]] = {}
    for address, value in rows_by_address.items():
        aid = as_text(address)
        if aid not in set(structure.addresses):
            continue
        titles = value if isinstance(value, list) else [value]
        title_rows.setdefault(aid, []).append({"row_id": aid, "identifier": aid, "label": as_text(titles[0] if titles else ""), "reference": ""})
    nodes = _build_nodes(structure, title_rows)
    return SamrasWorkspaceResource(
        structure_row_id=as_text(resource_body.get("resource_id")) or "resource",
        structure_label=as_text(resource_body.get("descriptor", {}).get("shape_root") if isinstance(resource_body.get("descriptor"), dict) else ""),
        structure=structure,
        nodes=nodes,
        title_reference="",
        title_layer=4,
        title_value_group=1,
        warnings=tuple(list(structure.warnings) + warnings),
    )


def _branch_context(workspace: SamrasWorkspaceResource, selected_address_id: str) -> dict[str, Any]:
    selected = as_text(selected_address_id)
    if not selected:
        return {
            "selected_address_id": "",
            "parent_address": "",
            "path_to_root": [],
            "siblings": [],
            "children": [],
            "next_child_preview": "",
            "child_count": 0,
            "sibling_index": None,
        }
    node_map = {node.address_id: node for node in workspace.nodes}
    node = node_map.get(selected)
    if node is None:
        return {
            "selected_address_id": selected,
            "parent_address": "",
            "path_to_root": [],
            "siblings": [],
            "children": [],
            "next_child_preview": "",
            "child_count": 0,
            "sibling_index": None,
        }
    path: list[str] = []
    cursor = selected
    while cursor:
        path.append(cursor)
        cursor = parent_address(cursor)
    path.reverse()
    siblings = [item.to_dict() for item in workspace.nodes if item.parent_address == node.parent_address]
    children = [node_map[address].to_dict() for address in node.child_addresses if address in node_map]
    next_child = f"{selected}-{node.child_count + 1}"
    sibling_index = None
    if node.parent_address:
        siblings_sorted = sorted([item.address_id for item in workspace.nodes if item.parent_address == node.parent_address], key=address_sort_key)
        sibling_index = siblings_sorted.index(selected) + 1 if selected in siblings_sorted else None
    return {
        "selected_address_id": selected,
        "parent_address": node.parent_address,
        "path_to_root": path,
        "siblings": siblings,
        "children": children,
        "next_child_preview": next_child,
        "child_count": node.child_count,
        "sibling_index": sibling_index,
    }


def build_workspace_view_model(
    workspace: SamrasWorkspaceResource,
    *,
    selected_address_id: str = "",
    staged_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = as_text(selected_address_id)
    if not selected and workspace.nodes:
        selected = workspace.nodes[0].address_id
    branch_context = _branch_context(workspace, selected)
    return {
        "schema": "mycite.portal.sandbox.samras_workspace.view_model.v2",
        "workspace_family": "samras_structure_tree",
        "structure_row_id": workspace.structure_row_id,
        "structure_label": workspace.structure_label,
        "canonical_magnitude": workspace.structure.bitstream,
        "structure": workspace.structure.to_dict(),
        "title_table_rows": [node.to_dict() for node in workspace.nodes],
        "branch_context": branch_context,
        "normalized_staged_entries": [dict(item) for item in list(staged_entries or []) if isinstance(item, dict)],
        "stage_warnings": [],
        "warnings": [str(item) for item in workspace.warnings],
    }


def _next_iteration(payload: dict[str, Any], *, layer: int, value_group: int) -> int:
    maximum = 0
    for key in dict(payload or {}).keys():
        parts = as_text(key).split("-")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            continue
        if int(parts[0], 10) != int(layer) or int(parts[1], 10) != int(value_group):
            continue
        maximum = max(maximum, int(parts[2], 10))
    return maximum + 1


def _rewrite_compact_payload(
    payload: dict[str, Any],
    *,
    workspace: SamrasWorkspaceResource,
    mutation: SamrasMutationResult,
    new_title: str = "",
    title_target_address: str = "",
) -> dict[str, Any]:
    updated: dict[str, Any] = {}
    removed = set(mutation.removed_addresses)
    mapping = dict(mutation.address_mapping)
    created = set(mutation.created_addresses)
    title_target = as_text(title_target_address)
    structure_written = False
    for row_key, raw_value in dict(payload or {}).items():
        record, _warnings, _valid = compact_row_to_record(as_text(row_key), raw_value)
        base = _raw_base(raw_value)
        labels = _raw_labels(raw_value)
        if as_text(row_key) == workspace.structure_row_id:
            updated[row_key] = [[as_text(row_key), "0-0-5", mutation.structure.bitstream], [labels[0] if labels else (workspace.structure_label or "samras")]]
            structure_written = True
            continue
        magnitude = as_text(record.get("magnitude"))
        if magnitude in removed:
            continue
        if magnitude in mapping and len(base) >= 3:
            base = [as_text(row_key), as_text(base[1]), mapping[magnitude]]
        updated[row_key] = [base, labels]
    if not structure_written:
        updated[workspace.structure_row_id] = [[workspace.structure_row_id, "0-0-5", mutation.structure.bitstream], [workspace.structure_label or "samras"]]
    if title_target and title_target in created:
        next_iteration = _next_iteration(updated, layer=workspace.title_layer, value_group=workspace.title_value_group)
        row_id = f"{workspace.title_layer}-{workspace.title_value_group}-{next_iteration}"
        updated[row_id] = [[row_id, workspace.title_reference, title_target], [new_title]]
    elif title_target and new_title:
        for row_key, raw_value in list(updated.items()):
            record, _warnings, _valid = compact_row_to_record(as_text(row_key), raw_value)
            if as_text(record.get("magnitude")) == title_target and _looks_like_address(as_text(record.get("magnitude"))):
                base = _raw_base(raw_value)
                labels = _raw_labels(raw_value)
                updated[row_key] = [base, [new_title or (labels[0] if labels else "")]]
                break
    return updated


def mutate_compact_payload(
    payload: dict[str, Any],
    *,
    action: str,
    address_id: str = "",
    parent_address: str = "",
    child_count: int | None = None,
    title: str = "",
) -> tuple[dict[str, Any], SamrasWorkspaceResource, dict[str, Any]]:
    workspace = load_workspace_from_compact_payload(payload)
    token = as_text(action).lower()
    if token == "samras_add_child":
        mutation = add_child(workspace.structure, parent_address=as_text(parent_address or address_id))
        target_address = mutation.created_addresses[0] if mutation.created_addresses else ""
        updated_payload = _rewrite_compact_payload(payload, workspace=workspace, mutation=mutation, new_title=as_text(title), title_target_address=target_address)
    elif token == "samras_create_root":
        mutation = add_root(workspace.structure)
        target_address = mutation.created_addresses[0] if mutation.created_addresses else ""
        updated_payload = _rewrite_compact_payload(payload, workspace=workspace, mutation=mutation, new_title=as_text(title), title_target_address=target_address)
    elif token == "samras_delete_branch":
        mutation = remove_branch(workspace.structure, address_id=as_text(address_id))
        updated_payload = _rewrite_compact_payload(payload, workspace=workspace, mutation=mutation)
    elif token == "samras_move_branch":
        mutation = move_branch(workspace.structure, from_address=as_text(address_id), to_parent_address=as_text(parent_address))
        updated_payload = _rewrite_compact_payload(payload, workspace=workspace, mutation=mutation)
    elif token == "samras_set_child_count":
        if child_count is None:
            raise InvalidSamrasStructure("child_count is required")
        mutation = set_child_count(workspace.structure, address_id=as_text(address_id), child_count=int(child_count))
        updated_payload = _rewrite_compact_payload(payload, workspace=workspace, mutation=mutation)
    elif token == "samras_update_title":
        noop = SamrasMutationResult(
            structure=workspace.structure,
            action=token,
            address_mapping={node.address_id: node.address_id for node in workspace.nodes},
            created_addresses=(),
            removed_addresses=(),
        )
        updated_payload = _rewrite_compact_payload(
            payload,
            workspace=workspace,
            mutation=noop,
            new_title=as_text(title),
            title_target_address=as_text(address_id),
        )
        mutation = noop
    else:
        raise InvalidSamrasStructure(f"unsupported SAMRAS action: {action}")
    updated_workspace = load_workspace_from_compact_payload(updated_payload)
    return updated_payload, updated_workspace, mutation.to_dict()


def mutate_resource_body(
    resource_body: dict[str, Any],
    *,
    action: str,
    address_id: str = "",
    parent_address: str = "",
    child_count: int | None = None,
    title: str = "",
) -> tuple[dict[str, Any], SamrasWorkspaceResource, dict[str, Any]]:
    workspace = load_workspace_from_resource_body(resource_body)
    token = as_text(action).lower()
    if token == "samras_add_child":
        mutation = add_child(workspace.structure, parent_address=as_text(parent_address or address_id))
    elif token == "samras_create_root":
        mutation = add_root(workspace.structure)
    elif token == "samras_delete_branch":
        mutation = remove_branch(workspace.structure, address_id=as_text(address_id))
    elif token == "samras_move_branch":
        mutation = move_branch(workspace.structure, from_address=as_text(address_id), to_parent_address=as_text(parent_address))
    elif token == "samras_set_child_count":
        if child_count is None:
            raise InvalidSamrasStructure("child_count is required")
        mutation = set_child_count(workspace.structure, address_id=as_text(address_id), child_count=int(child_count))
    else:
        raise InvalidSamrasStructure(f"unsupported SAMRAS action: {action}")

    rows_by_address = resource_body.get("rows_by_address") if isinstance(resource_body.get("rows_by_address"), dict) else {}
    new_rows_by_address: dict[str, list[str]] = {}
    removed = set(mutation.removed_addresses)
    mapping = dict(mutation.address_mapping)
    for key, value in rows_by_address.items():
        aid = as_text(key)
        if aid in removed:
            continue
        next_key = mapping.get(aid, aid)
        titles = value if isinstance(value, list) else [value]
        new_rows_by_address[next_key] = [as_text(titles[0] if titles else "")]
    if mutation.created_addresses and as_text(title):
        new_rows_by_address[mutation.created_addresses[0]] = [as_text(title)]
    updated = dict(resource_body)
    updated["structure_payload"] = mutation.structure.bitstream
    updated["canonical_magnitude"] = mutation.structure.bitstream
    updated["samras_structure"] = mutation.structure.to_dict()
    updated["root_ref"] = mutation.structure.root_ref
    updated["source_format"] = mutation.structure.source_format
    updated["canonical_state"] = "canonical"
    updated["rows_by_address"] = new_rows_by_address
    updated_workspace = load_workspace_from_resource_body(updated)
    return updated, updated_workspace, mutation.to_dict()
