from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from types import ModuleType


def _load_shared_inherited_taxonomy() -> ModuleType:
    try:
        return importlib.import_module("_shared.portal.services.inherited_taxonomy")
    except Exception:
        pass
    shared_path = Path(__file__).resolve().parents[3] / "_shared" / "portal" / "services" / "inherited_taxonomy.py"
    spec = importlib.util.spec_from_file_location("mycite_shared_inherited_taxonomy", shared_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared inherited taxonomy service from {shared_path}")
    module = importlib.util.module_from_spec(spec)
    # mypy and type checkers can treat this as an opaque module; we only re-export selected names.
    importlib.util.module_from_spec
    spec.loader.exec_module(module)
    return module


_SHARED = _load_shared_inherited_taxonomy()

load_inherited_taxonomy = _SHARED.load_inherited_taxonomy

