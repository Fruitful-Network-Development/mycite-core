from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mycite_core.runtime_host.state_roots import instance_state_root


@dataclass(frozen=True)
class PortalInstanceDeclaration:
    portal_id: str
    portal_instance_id: str
    runtime_flavor: str
    state_dir: Path


def _declaration(portal_id: str, portal_instance_id: str, runtime_flavor: str) -> PortalInstanceDeclaration:
    return PortalInstanceDeclaration(
        portal_id=portal_id,
        portal_instance_id=portal_instance_id,
        runtime_flavor=runtime_flavor,
        state_dir=instance_state_root(portal_instance_id),
    )


ACTIVE_PORTAL_DECLARATIONS: dict[str, PortalInstanceDeclaration] = {
    "mycite-le_example": _declaration("mycite-le_example", "example", "tff"),
    "mycite-le_fnd": _declaration("mycite-le_fnd", "fnd", "fnd"),
    "mycite-le_tff": _declaration("mycite-le_tff", "tff", "tff"),
}


def portal_declaration(portal_id: str) -> PortalInstanceDeclaration:
    if portal_id not in ACTIVE_PORTAL_DECLARATIONS:
        raise ValueError(f"No active portal declaration configured for {portal_id}")
    return ACTIVE_PORTAL_DECLARATIONS[portal_id]


def default_state_root_for(portal_id: str) -> Path:
    return portal_declaration(portal_id).state_dir


def default_portal_instance_id_for(portal_id: str) -> str:
    return portal_declaration(portal_id).portal_instance_id


def default_runtime_flavor_for(portal_id: str) -> str:
    return portal_declaration(portal_id).runtime_flavor
