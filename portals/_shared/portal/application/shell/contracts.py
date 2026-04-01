from __future__ import annotations

import sys
from pathlib import Path


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "portals").exists() and (parent / "portal_core").exists():
            return parent
    raise RuntimeError("Unable to resolve mycite-core repo root")


REPO_ROOT = _repo_root()
token = str(REPO_ROOT)
if token not in sys.path:
    sys.path.insert(0, token)

from portal_core.shell.contracts import *  # noqa: F401,F403
