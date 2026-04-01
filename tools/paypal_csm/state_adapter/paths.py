from __future__ import annotations

from pathlib import Path

from tools._shared.tool_state_api.paths import tool_state_members_dir, tool_state_root


def paypal_csm_state_root(private_dir: Path) -> Path:
    return tool_state_root(private_dir, "paypal-csm")


def paypal_csm_tenants_dir(private_dir: Path) -> Path:
    return tool_state_members_dir(private_dir, "paypal-csm", "tenants")

