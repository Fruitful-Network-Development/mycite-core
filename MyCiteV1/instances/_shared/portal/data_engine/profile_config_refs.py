from __future__ import annotations

from copy import deepcopy
from typing import Any


def _index_token(token: str) -> int | None:
    try:
        value = int(str(token or "").strip())
    except Exception:
        return None
    return value if value >= 0 else None


def get_path(payload: dict[str, Any], path: str) -> Any:
    def _walk(node: Any, tokens: list[str], *, property_list_alias: bool = False) -> Any:
        if not tokens:
            return node
        token = tokens[0]
        if isinstance(node, dict):
            return _walk(node.get(token), tokens[1:], property_list_alias=(token == "property"))
        if isinstance(node, list):
            index = _index_token(token)
            if index is not None:
                if index >= len(node):
                    return None
                return _walk(node[index], tokens[1:])
            if not property_list_alias or not node or not isinstance(node[0], (dict, list)):
                return None
            return _walk(node[0], tokens)
        return None

    return _walk(payload, [part for part in str(path or "").split(".") if part])


def set_path(payload: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    tokens = [part for part in str(path or "").split(".") if part]
    if not tokens:
        return deepcopy(payload if isinstance(payload, dict) else {})

    def _default_container(next_token: str | None, current_token: str = "") -> Any:
        if current_token == "property" and (next_token is None or _index_token(next_token) is None):
            return [{}]
        if next_token is not None and _index_token(next_token) is not None:
            return []
        return {}

    def _assign(node: Any, remaining: list[str], next_value: Any, *, property_list_alias: bool = False) -> Any:
        if not remaining:
            return next_value

        token = remaining[0]
        tail = remaining[1:]

        if isinstance(node, dict):
            out = deepcopy(node)
            if not tail:
                out[token] = next_value
                return out
            child = out.get(token)
            if not isinstance(child, (dict, list)):
                child = _default_container(tail[0], token)
            out[token] = _assign(child, tail, next_value, property_list_alias=(token == "property"))
            return out

        if isinstance(node, list):
            out = list(node)
            index = _index_token(token)
            if index is not None:
                while len(out) <= index:
                    out.append(_default_container(tail[0] if tail else None))
                child = out[index]
                if not tail:
                    out[index] = next_value
                    return out
                if not isinstance(child, (dict, list)):
                    child = _default_container(tail[0])
                out[index] = _assign(child, tail, next_value)
                return out

            if not property_list_alias:
                return out
            if not out:
                out.append({})
            first = out[0]
            if not isinstance(first, (dict, list)):
                first = {}
            out[0] = _assign(first, remaining, next_value)
            return out

        return _assign(_default_container(token), remaining, next_value)

    base = deepcopy(payload if isinstance(payload, dict) else {})
    return _assign(base, tokens, value)


def append_unique_path_value(payload: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    current = get_path(payload if isinstance(payload, dict) else {}, path)
    current_items = current if isinstance(current, list) else []
    token = value
    out_list = [item for item in current_items if str(item or "").strip()]
    if str(token or "").strip() and token not in out_list:
        out_list.append(token)
    return set_path(payload if isinstance(payload, dict) else {}, path, out_list)
