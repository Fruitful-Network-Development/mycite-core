"""
TXA sandbox workspace helpers — view models for title-carrying SAMRAS resources.

These functions are **presentation and preview** helpers: they assemble branch context,
title tables, and next-child address previews from a sandbox resource payload plus
optional **staged** entries. They do **not** persist; promotion remains
``SandboxEngine`` / ``LocalResourceLifecycleService`` / tool session paths.

Follow-up (reverse sync): see ``docs/txa_sandbox_workspace_pass.md``.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from _shared.portal.sandbox.samras import decode_resource_rows

_ADDR_RE = re.compile(r"^[0-9]+(?:-[0-9]+)*$")


def samras_parent_address(address_id: str) -> str:
    token = str(address_id or "").strip()
    if not token:
        return ""
    parts = token.split("-")
    if len(parts) <= 1:
        return ""
    return "-".join(parts[:-1])


def samras_depth(address_id: str) -> int:
    token = str(address_id or "").strip()
    if not token:
        return 0
    return len(token.split("-"))


def _row_address(row: Mapping[str, Any]) -> str:
    return str(row.get("address_id") or row.get("row_id") or "").strip()


def samras_direct_children_rows(parent_address: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    parent = str(parent_address or "").strip()
    if not parent:
        return []
    pd = samras_depth(parent)
    out: list[dict[str, Any]] = []
    for row in rows:
        cid = _row_address(row)
        if not cid or _ADDR_RE.fullmatch(cid) is None:
            continue
        if samras_parent_address(cid) != parent:
            continue
        if samras_depth(cid) != pd + 1:
            continue
        out.append(dict(row))
    out.sort(key=lambda r: tuple(int(p) for p in _row_address(r).split("-")))
    return out


def samras_next_child_address(parent_address: str, rows: Sequence[Mapping[str, Any]]) -> str:
    parent = str(parent_address or "").strip()
    if not parent:
        return ""
    max_seg = 0
    for row in samras_direct_children_rows(parent, rows):
        cid = _row_address(row)
        parts = cid.split("-")
        try:
            tail = int(parts[-1], 10)
        except (ValueError, IndexError):
            continue
        if tail > max_seg:
            max_seg = tail
    return f"{parent}-{max_seg + 1}"


def samras_next_root_address(rows: Sequence[Mapping[str, Any]]) -> str:
    max_root = 0
    for row in rows:
        cid = _row_address(row)
        if not cid:
            continue
        parts = cid.split("-")
        if len(parts) != 1:
            continue
        try:
            v = int(parts[0], 10)
        except ValueError:
            continue
        if v > max_root:
            max_root = v
    return str(max_root + 1)


def path_to_root(address_id: str) -> list[str]:
    """Root-most first (e.g. ['1','1-1','1-1-3'])."""
    token = str(address_id or "").strip()
    if not token:
        return []
    chain: list[str] = []
    cur = token
    while cur:
        chain.append(cur)
        cur = samras_parent_address(cur)
    chain.reverse()
    return chain


def sibling_rows(selected_address: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sel = str(selected_address or "").strip()
    if not sel:
        return []
    parent = samras_parent_address(sel)
    if parent:
        return [dict(r) for r in samras_direct_children_rows(parent, rows)]
    # roots: depth 1
    out: list[dict[str, Any]] = []
    for row in rows:
        cid = _row_address(row)
        if samras_depth(cid) == 1:
            out.append(dict(row))
    out.sort(key=lambda r: tuple(int(p) for p in _row_address(r).split("-")))
    return out


def normalize_staged_entries(
    persisted_rows: list[dict[str, Any]],
    staged_entries: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Assign ``provisional_child_address`` for each staged entry (next free child under parent).
    Returns (normalized_staged, warnings).
    """
    warnings: list[str] = []
    combined: list[dict[str, Any]] = [dict(r) for r in persisted_rows]
    used = {_row_address(r) for r in combined if _row_address(r)}
    normalized: list[dict[str, Any]] = []
    for raw in staged_entries:
        if not isinstance(raw, Mapping):
            continue
        parent = str(raw.get("parent_address") or "").strip()
        title = str(raw.get("title") or raw.get("name") or "").strip()
        prov = str(raw.get("provisional_child_address") or raw.get("provisional_address") or "").strip()
        if not parent:
            warnings.append("skipped staged entry: parent_address required")
            continue
        if not title:
            warnings.append("skipped staged entry: title required")
            continue
        if not prov:
            prov = samras_next_child_address(parent, combined)
        if prov in used:
            warnings.append(f"skipped staged entry: address already used: {prov}")
            continue
        used.add(prov)
        entry = {
            "parent_address": parent,
            "title": title,
            "provisional_child_address": prov,
            "status": "staged",
        }
        normalized.append(entry)
        combined.append({"address_id": prov, "title": title, "status": "staged"})
    return normalized, warnings


def build_title_table_rows(
    persisted_rows: list[dict[str, Any]],
    normalized_staged: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in persisted_rows:
        aid = _row_address(row)
        if not aid:
            continue
        out.append(
            {
                "address_id": aid,
                "title": str(row.get("title") or row.get("name") or "").strip(),
                "parent_address": samras_parent_address(aid),
                "depth": samras_depth(aid),
                "status": "saved",
            }
        )
    for st in normalized_staged:
        prov = str(st.get("provisional_child_address") or "").strip()
        if not prov:
            continue
        out.append(
            {
                "address_id": prov,
                "title": str(st.get("title") or "").strip(),
                "parent_address": str(st.get("parent_address") or "").strip(),
                "depth": samras_depth(prov),
                "status": "staged",
            }
        )
    out.sort(key=lambda r: tuple(int(p) for p in str(r["address_id"]).split("-")))
    return out


def build_branch_context(
    selected_address_id: str,
    combined_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sel = str(selected_address_id or "").strip()
    if not sel:
        return {
            "selected_address_id": "",
            "parent_address": "",
            "path_to_root": [],
            "siblings": [],
            "children": [],
            "next_child_preview": "",
            "sibling_index": None,
            "child_count": 0,
        }
    parent = samras_parent_address(sel)
    sibs = sibling_rows(sel, combined_rows)
    children = samras_direct_children_rows(sel, combined_rows)
    next_ch = samras_next_child_address(sel, combined_rows)
    sib_ids = [_row_address(s) for s in sibs]
    sib_index = sib_ids.index(sel) if sel in sib_ids else None
    return {
        "selected_address_id": sel,
        "parent_address": parent,
        "path_to_root": path_to_root(sel),
        "siblings": [
            {
                "address_id": _row_address(s),
                "title": str(s.get("title") or s.get("name") or "").strip(),
                "is_selected": _row_address(s) == sel,
            }
            for s in sibs
        ],
        "children": [
            {
                "address_id": _row_address(c),
                "title": str(c.get("title") or c.get("name") or "").strip(),
            }
            for c in children
        ],
        "next_child_preview": next_ch,
        "sibling_index": sib_index,
        "child_count": len(children),
    }


def build_txa_sandbox_view_model(
    resource_payload: Mapping[str, Any],
    *,
    selected_address_id: str = "",
    staged_entries: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Assemble a JSON-serializable view model for the TXA sandbox UI.

    ``resource_payload`` is a sandbox ``get_resource`` dict (not the ``missing`` sentinel).
    """
    staged_entries = list(staged_entries or [])
    payload = dict(resource_payload)
    persisted = decode_resource_rows(payload)
    normalized_staged, stage_warnings = normalize_staged_entries(persisted, staged_entries)
    combined: list[dict[str, Any]] = [dict(r) for r in persisted]
    for st in normalized_staged:
        prov = str(st.get("provisional_child_address") or "").strip()
        combined.append(
            {
                "address_id": prov,
                "title": str(st.get("title") or "").strip(),
                "status": "staged",
            }
        )

    table_rows = build_title_table_rows(persisted, normalized_staged)
    branch = build_branch_context(selected_address_id, combined)
    rid = str(payload.get("resource_id") or "").strip()
    kind = str(payload.get("resource_kind") or payload.get("kind") or "").strip()

    return {
        "schema": "mycite.portal.sandbox.txa_workspace.view_model.v1",
        "resource_id": rid,
        "resource_kind": kind,
        "persisted_row_count": len(persisted),
        "normalized_staged_entries": normalized_staged,
        "title_table_rows": table_rows,
        "combined_rows": combined,
        "branch_context": branch,
        "stage_warnings": stage_warnings,
        "notes": (
            "Staged entries are preview-only until promoted via sandbox save / lifecycle. "
            "Reverse SAMRAS sync is a follow-up phase."
        ),
    }


def build_samras_workspace_view_model(
    resource_payload: Mapping[str, Any],
    *,
    selected_address_id: str = "",
    staged_entries: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    SAMRAS title-tree workspace view (TXA, MSN, future SAMRAS-backed resources).

    Same row/branch grammar as :func:`build_txa_sandbox_view_model`; schema id reflects
    shared SAMRAS capability rather than TXA-only naming.
    """
    vm = build_txa_sandbox_view_model(
        resource_payload,
        selected_address_id=selected_address_id,
        staged_entries=staged_entries,
    )
    vm["schema"] = "mycite.portal.sandbox.samras_workspace.view_model.v1"
    vm["workspace_family"] = "samras_title_tree"
    return vm


__all__ = [
    "build_branch_context",
    "build_samras_workspace_view_model",
    "build_title_table_rows",
    "build_txa_sandbox_view_model",
    "normalize_staged_entries",
    "path_to_root",
    "samras_depth",
    "samras_direct_children_rows",
    "samras_next_child_address",
    "samras_next_root_address",
    "samras_parent_address",
    "sibling_rows",
]
