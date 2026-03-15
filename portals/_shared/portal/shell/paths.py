from __future__ import annotations

from pathlib import Path


def canonical_shell_template_dir(portals_root: Path) -> Path:
    return portals_root / "_shared" / "runtime" / "flavors" / "fnd" / "portal" / "ui" / "templates"


def canonical_shell_static_dir(portals_root: Path) -> Path:
    return portals_root / "_shared" / "runtime" / "flavors" / "fnd" / "portal" / "ui" / "static"
