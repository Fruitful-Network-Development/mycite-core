from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from pathlib import Path
from types import ModuleType


def _text(value: object, default: str = "") -> str:
    token = default if value is None else str(value)
    return token.strip()


def _reset_portal_namespace() -> None:
    for key in list(sys.modules):
        if key == "portal" or key.startswith("portal."):
            sys.modules.pop(key, None)


def load_runtime_flavor_module(portals_root: Path, flavor: str) -> ModuleType:
    token = _text(flavor, "fnd").lower() or "fnd"
    flavor_root = Path(portals_root) / "_shared" / "runtime" / "flavors" / token
    app_path = flavor_root / "app.py"
    if not app_path.exists():
        raise RuntimeError(f"Unsupported portal runtime flavor: {token}")
    if str(flavor_root) not in sys.path:
        sys.path.insert(0, str(flavor_root))
    _reset_portal_namespace()
    module_name = f"mycite_runtime_{token}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load portal runtime flavor: {token}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_runtime_flavor_module_from_env(default_portals_root: Path) -> ModuleType:
    flavor = _text(os.environ.get("PORTAL_RUNTIME_FLAVOR"), "fnd").lower() or "fnd"
    return load_runtime_flavor_module(default_portals_root, flavor)

