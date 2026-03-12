from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_contract_handshake() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "api" / "contract_handshake.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_contract_handshake", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared contract handshake routes from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_contract_handshake()

register_contract_handshake_routes = _SHARED.register_contract_handshake_routes
