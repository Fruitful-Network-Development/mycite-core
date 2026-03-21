from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _text(value: object, default: str = "") -> str:
    token = default if value is None else str(value)
    return token.strip()


@dataclass(frozen=True)
class PortalInstanceContext:
    portals_root: Path
    public_dir: Path
    private_dir: Path
    data_dir: Path
    portal_instance_id: str
    portal_runtime_flavor: str
    msn_id: str
    portal_entry_path: str
    default_embed_port: str
    sign_out_url: str
    switch_portal_url: str


def build_instance_context_from_env(
    *,
    default_portals_root: Path,
    default_public_dir: Path,
    default_private_dir: Path,
    default_data_dir: Path,
    default_portal_instance_id: str,
    default_portal_runtime_flavor: str,
    default_portal_entry_path: str = "",
    default_embed_port: str = "",
) -> PortalInstanceContext:
    portals_root = Path(_text(os.environ.get("MYCITE_PORTALS_ROOT"), str(default_portals_root)) or str(default_portals_root))
    public_dir = Path(_text(os.environ.get("PUBLIC_DIR"), str(default_public_dir)) or str(default_public_dir))
    private_dir = Path(_text(os.environ.get("PRIVATE_DIR"), str(default_private_dir)) or str(default_private_dir))
    data_dir = Path(_text(os.environ.get("DATA_DIR"), str(default_data_dir)) or str(default_data_dir))
    portal_instance_id = _text(os.environ.get("PORTAL_INSTANCE_ID"), default_portal_instance_id) or default_portal_instance_id
    portal_runtime_flavor = _text(os.environ.get("PORTAL_RUNTIME_FLAVOR"), default_portal_runtime_flavor) or default_portal_runtime_flavor
    msn_id = _text(os.environ.get("MSN_ID"))
    portal_entry_path = _text(os.environ.get("PORTAL_ENTRY_PATH"), default_portal_entry_path)
    default_embed_port = _text(os.environ.get("DEFAULT_EMBED_PORT"), default_embed_port)
    sign_out_url = _text(os.environ.get("PORTAL_SIGN_OUT_URL"))
    switch_portal_url = _text(os.environ.get("PORTAL_SWITCH_URL"))
    return PortalInstanceContext(
        portals_root=portals_root,
        public_dir=public_dir,
        private_dir=private_dir,
        data_dir=data_dir,
        portal_instance_id=portal_instance_id,
        portal_runtime_flavor=portal_runtime_flavor,
        msn_id=msn_id,
        portal_entry_path=portal_entry_path,
        default_embed_port=default_embed_port,
        sign_out_url=sign_out_url,
        switch_portal_url=switch_portal_url,
    )
