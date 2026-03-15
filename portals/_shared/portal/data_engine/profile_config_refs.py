from __future__ import annotations

from copy import deepcopy
from typing import Any


def get_path(payload: dict[str, Any], path: str) -> Any:
    node: Any = payload
    for token in [part for part in str(path or "").split(".") if part]:
        if not isinstance(node, dict):
            return None
        node = node.get(token)
    return node


def set_path(payload: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    out = deepcopy(payload if isinstance(payload, dict) else {})
    tokens = [part for part in str(path or "").split(".") if part]
    if not tokens:
        return out
    node: dict[str, Any] = out
    for token in tokens[:-1]:
        child = node.get(token)
        if not isinstance(child, dict):
            child = {}
            node[token] = child
        node = child
    node[tokens[-1]] = value
    return out
