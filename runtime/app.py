from __future__ import annotations

import sys
from pathlib import Path

from portal_core.composition.runtime_loader import load_runtime_flavor_module_from_env

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTALS_ROOT = REPO_ROOT / "portals"

for _path in (REPO_ROOT, PORTALS_ROOT):
    token = str(_path)
    if token not in sys.path:
        sys.path.insert(0, token)

_runtime_module = load_runtime_flavor_module_from_env(PORTALS_ROOT)
for _key, _value in vars(_runtime_module).items():
    if _key.startswith("__"):
        continue
    globals()[_key] = _value

app = globals()["app"]

