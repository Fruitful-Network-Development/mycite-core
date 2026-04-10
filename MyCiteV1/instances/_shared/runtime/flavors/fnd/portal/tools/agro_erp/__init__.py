from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_tff_agro_module() -> ModuleType:
    shared_path = Path(__file__).resolve().parents[4] / "tff" / "portal" / "tools" / "agro_erp" / "__init__.py"
    spec = importlib.util.spec_from_file_location("mycite_tff_agro_erp_tool", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared AGRO ERP tool module from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED = _load_tff_agro_module()

get_tool = _SHARED.get_tool

