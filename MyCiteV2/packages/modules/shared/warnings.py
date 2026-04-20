from __future__ import annotations

from .scalars import as_text


def dedupe_warnings(*groups: object) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            token = as_text(item)
            if not token or token in seen:
                continue
            seen.add(token)
            out.append(token)
    return out


__all__ = [
    "dedupe_warnings",
]
