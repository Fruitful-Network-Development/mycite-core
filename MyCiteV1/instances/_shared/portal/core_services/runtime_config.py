from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PortalRuntimeConfig:
    private_dir: Path
    public_dir: Path
    data_dir: Path
    msn_id: str
    portal_instance_id: str


def build_runtime_config(
    *,
    private_dir: Path,
    public_dir: Path,
    data_dir: Path,
    msn_id: str,
    portal_instance_id: str,
) -> PortalRuntimeConfig:
    return PortalRuntimeConfig(
        private_dir=private_dir,
        public_dir=public_dir,
        data_dir=data_dir,
        msn_id=str(msn_id or "").strip(),
        portal_instance_id=str(portal_instance_id or "").strip().lower(),
    )
