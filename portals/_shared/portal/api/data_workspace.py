from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_flavor_data_workspace():
    portals_root = Path(__file__).resolve().parents[3]
    source_path = portals_root / "_shared" / "runtime" / "flavors" / "fnd" / "portal" / "api" / "data_workspace.py"
    spec = importlib.util.spec_from_file_location("_shared_portal_data_workspace_impl", source_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load canonical data workspace registrar")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_flavor_data_workspace()
register_data_routes = _MODULE.register_data_routes
