from __future__ import annotations

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


REPO_ROOT = _repo_root()
for path in (REPO_ROOT, REPO_ROOT / "instances", REPO_ROOT / "packages"):
    token = str(path)
    if token not in sys.path:
        sys.path.insert(0, token)

from mycite_core.runtime_host.runtime_loader import load_runtime_flavor_module_from_env


PORTALS_ROOT = Path(str(os.environ.get("MYCITE_PORTALS_ROOT") or (REPO_ROOT / "instances")))
RUNTIME_MODULE = load_runtime_flavor_module_from_env(PORTALS_ROOT)
app = RUNTIME_MODULE.app


def __getattr__(name: str):
    return getattr(RUNTIME_MODULE, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(RUNTIME_MODULE)))
