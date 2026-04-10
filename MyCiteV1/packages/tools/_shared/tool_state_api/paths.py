from __future__ import annotations

from pathlib import Path

from mycite_core.runtime_paths import utility_tools_dir


def tool_state_root(private_dir: Path, namespace: str, *, create: bool = True) -> Path:
    slug = str(namespace or "").strip()
    if not slug:
        raise ValueError("namespace is required")
    root = utility_tools_dir(Path(private_dir)) / slug
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def tool_state_members_dir(private_dir: Path, namespace: str, collection: str, *, create: bool = True) -> Path:
    root = tool_state_root(private_dir, namespace, create=create)
    target = root / collection
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target
