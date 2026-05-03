"""Shared address and profile utilities for CTS-GIS internal modules."""

from __future__ import annotations

from typing import Any

from MyCiteV2.packages.modules.cross_domain.cts_gis.contracts import as_text as _as_text


def _as_lower(value: object) -> str:
    return _as_text(value).lower()


def _address_tuple(value: object) -> tuple[int, ...]:
    token = _as_text(value)
    if not token or any(not part.isdigit() for part in token.split("-")):
        return ()
    return tuple(int(part) for part in token.split("-"))


def _node_depth(node_id: object) -> int:
    return len(_address_tuple(node_id))


def _parent_node_id(node_id: object) -> str:
    parts = _address_tuple(node_id)
    if len(parts) <= 1:
        return ""
    return "-".join(str(part) for part in parts[:-1])


def _first_non_empty(values: list[object] | tuple[object, ...]) -> str:
    for value in values:
        token = _as_text(value)
        if token:
            return token
    return ""


def _sorted_addresses(values: set[str] | list[str] | tuple[str, ...]) -> list[str]:
    return sorted(
        (_as_text(value) for value in values if _as_text(value)),
        key=lambda item: (_address_tuple(item) or (10**9,), item),
    )


def _address_is_descendant(
    node_id: str,
    *,
    root_node_id: str,
    min_extra_segments: int,
    max_extra_segments: int,
) -> bool:
    node_parts = _address_tuple(node_id)
    root_parts = _address_tuple(root_node_id)
    if not node_parts or not root_parts or len(node_parts) <= len(root_parts):
        return False
    if tuple(node_parts[: len(root_parts)]) != tuple(root_parts):
        return False
    extra_segments = len(node_parts) - len(root_parts)
    return min_extra_segments <= extra_segments <= max_extra_segments


def _profile_sort_key(profile: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(profile.get("depth") or 10**6),
        0 if profile.get("child_count") else 1,
        0 if profile.get("feature_count") else 1,
        _as_text(profile.get("node_id")),
    )
