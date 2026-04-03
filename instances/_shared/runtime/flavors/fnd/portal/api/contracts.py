from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_contract_routes() -> ModuleType:
    app_root = Path(__file__).resolve().parents[3]
    app_root_token = str(app_root)
    if app_root_token not in sys.path:
        sys.path.insert(0, app_root_token)
    return importlib.import_module("_shared.portal.api.contracts")


_SHARED = _load_shared_contract_routes()

register_contract_routes = _SHARED.register_contract_routes
