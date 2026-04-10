from __future__ import annotations

from pathlib import Path

from tools._shared.tool_state_api.paths import tool_state_root


def analytics_state_root(private_dir: Path) -> Path:
    return tool_state_root(private_dir, "fnd-ebi")

