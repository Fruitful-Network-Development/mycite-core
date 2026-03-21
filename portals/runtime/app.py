from __future__ import annotations

import importlib.util
import os
import sys
import uuid
from pathlib import Path

RUNTIME_DIR = Path(__file__).resolve().parent
PORTALS_ROOT = RUNTIME_DIR.parent
if str(PORTALS_ROOT) not in sys.path:
    sys.path.insert(0, str(PORTALS_ROOT))


def _load_flavor_module():
    flavor = str(os.environ.get("PORTAL_RUNTIME_FLAVOR") or "fnd").strip().lower() or "fnd"
    flavor_root = PORTALS_ROOT / "_shared" / "runtime" / "flavors" / flavor
    app_path = flavor_root / "app.py"
    if not app_path.exists():
        raise RuntimeError(f"Unsupported portal runtime flavor: {flavor}")
    if str(flavor_root) not in sys.path:
        sys.path.insert(0, str(flavor_root))
    existing_portal = sys.modules.get("portal")
    if existing_portal is not None:
        existing_file = str(getattr(existing_portal, "__file__", "") or "")
        if existing_file and not existing_file.startswith(str(flavor_root)):
            for key in list(sys.modules):
                if key == "portal" or key.startswith("portal."):
                    sys.modules.pop(key, None)
    module_name = f"mycite_runtime_{flavor}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load portal runtime flavor: {flavor}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_runtime_module = _load_flavor_module()
for _key, _value in vars(_runtime_module).items():
    if _key.startswith("__"):
        continue
    globals()[_key] = _value

app = globals()["app"]
