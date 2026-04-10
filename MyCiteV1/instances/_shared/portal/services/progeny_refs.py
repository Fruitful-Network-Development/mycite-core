from __future__ import annotations

from typing import Any


def iter_progeny_refs(raw: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _push(progeny_type: str, ref_token: Any) -> None:
        t = str(progeny_type or "").strip().lower()
        r = str(ref_token or "").strip()
        if not t or not r:
            return
        out.append((t, r))

    def _walk(node: Any, fallback_type: str = "") -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item, fallback_type=fallback_type)
            return
        if isinstance(node, dict):
            explicit_type = str(node.get("progeny_type") or node.get("type") or fallback_type or "").strip().lower()
            explicit_ref = node.get("ref") or node.get("path") or node.get("file") or node.get("source")
            if explicit_type and explicit_ref:
                _push(explicit_type, explicit_ref)
                refs = node.get("refs")
                if isinstance(refs, list):
                    for ref in refs:
                        _push(explicit_type, ref)
                return
            for key, value in node.items():
                key_token = str(key or "").strip().lower()
                if key_token in {"progeny_type", "type", "ref", "path", "file", "source", "refs"}:
                    continue
                if isinstance(value, str):
                    _push(key_token or fallback_type, value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            _push(key_token or fallback_type, item)
                        else:
                            _walk(item, fallback_type=key_token or fallback_type)
                else:
                    _walk(value, fallback_type=key_token or fallback_type)

    _walk(raw)
    return out
