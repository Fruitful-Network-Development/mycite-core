from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_INSTANCES_ROOT = Path("/srv/mycite-state/instances")


def _text(value: object, default: str = "") -> str:
    token = default if value is None else str(value)
    return token.strip()


def canonical_instances_root(default: Path | str = DEFAULT_INSTANCES_ROOT) -> Path:
    token = _text(os.environ.get("MYCITE_INSTANCES_ROOT"), str(default)) or str(default)
    return Path(token)


def infer_instance_state_root(
    *,
    public_dir: Path | None = None,
    private_dir: Path | None = None,
    data_dir: Path | None = None,
    explicit: str | Path | None = None,
) -> Path | None:
    if explicit:
        return Path(str(explicit))
    candidates = [path.parent for path in (public_dir, private_dir, data_dir) if isinstance(path, Path)]
    if candidates and all(path == candidates[0] for path in candidates):
        return candidates[0]
    return None


def instance_state_root(
    instance_id: str,
    *,
    explicit: str | Path | None = None,
    instances_root: Path | None = None,
) -> Path:
    resolved = infer_instance_state_root(explicit=explicit)
    if resolved is not None:
        return resolved
    token = _text(instance_id)
    if not token:
        raise ValueError("instance_id is required")
    root = instances_root or canonical_instances_root()
    return Path(root) / token


@dataclass(frozen=True)
class InstanceStateDirs:
    state_root: Path
    app_dir: Path
    public_dir: Path
    private_dir: Path
    data_dir: Path
    sandboxes_dir: Path
    contracts_dir: Path
    vault_dir: Path
    logs_dir: Path


def build_instance_state_dirs(
    instance_id: str,
    *,
    state_root: Path | None = None,
    instances_root: Path | None = None,
) -> InstanceStateDirs:
    resolved_root = state_root or instance_state_root(instance_id, instances_root=instances_root)
    return InstanceStateDirs(
        state_root=resolved_root,
        app_dir=resolved_root / "app",
        public_dir=resolved_root / "public",
        private_dir=resolved_root / "private",
        data_dir=resolved_root / "data",
        sandboxes_dir=resolved_root / "sandboxes",
        contracts_dir=resolved_root / "contracts",
        vault_dir=resolved_root / "vault" / "keypass",
        logs_dir=resolved_root / "logs",
    )

